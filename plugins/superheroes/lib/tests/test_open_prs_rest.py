"""Conformance: every read of the open-PR list goes through `stack_check.list_open_prs`, which reads `gh pr list`
first and re-reads the same list through REST only when that call is the cloud proxy's GraphQL refusal (#2118).
The fixtures are real recorded responses (cloud_rest/, stack_rest/). Nothing here runs gh, touches the network or
reads the real home directory."""
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

import gh_pages  # noqa: E402
import launcher as L  # noqa: E402
import review_record  # noqa: E402
import stack_check as sc  # noqa: E402
import wave_watch  # noqa: E402

_FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
_PAGE_RE = re.compile(r"^repos/\{owner\}/\{repo\}/pulls\?state=open&sort=created&direction=desc&per_page=100&page=(\d+)$")
_FIELDS = ("number", "headRefOid", "state")
_PULLS_PATH = "repos/{owner}/{repo}/pulls?state=open&sort=created&direction=desc"


def _fixture(*parts):
    with open(os.path.join(_FIXTURES, *parts), encoding="utf-8") as fh:
        return fh.read()


_PULLS_PAGE1 = json.loads(_fixture("cloud_rest", "pulls_open_page1.json"))
_LIST_REFUSED_STDERR = _fixture("cloud_rest", "gh_pr_list_refused.stderr")
_REPO_VIEW_REFUSED_STDERR = _fixture("stack_rest", "graphql_refused.stderr")
_REPOS_JSON = _fixture("stack_rest", "repos_superheroes.json")


def _graphql_rows(pulls):
    return [{"number": p["number"], "headRefOid": p["head"]["sha"], "state": "OPEN"} for p in pulls]


def _sha(n):
    return "%040x" % n


def _pull(n, sha=None):
    return {"number": n, "state": "open", "head": {"sha": sha or _sha(n)}}


def _proc(rc=0, out="", err=""):
    return SimpleNamespace(returncode=rc, stdout=out, stderr=err)


class FakeGh:
    """A fake `run` serving the fixtures by argv. `list_mode` is "ok" (GraphQL rows), "refused" (the recorded proxy
    refusal) or "error" (`list_stderr`, exit 1). REST pages serve `pulls` 100 a page; `fail_pages` answer exit 1,
    `junk_pages` answer a body that is not JSON, `object_pages` answer a JSON object. `on_call(argv)` runs first on
    every call. Every argv and its kwargs are recorded."""

    def __init__(self, pulls, list_mode="refused", list_stderr="", fail_pages=(), junk_pages=(), object_pages=(),
                 on_call=None):
        self.pulls, self.list_mode, self.list_stderr = pulls, list_mode, list_stderr
        self.fail_pages, self.junk_pages, self.object_pages = set(fail_pages), set(junk_pages), set(object_pages)
        self.on_call = on_call
        self.calls = []

    @property
    def rest_calls(self):
        return [c for c in self.calls if c[:2] == ["gh", "api"] and "/pulls?" in c[2]]

    @property
    def pages_asked(self):
        return [int(_PAGE_RE.match(c[2]).group(1)) for c in self.rest_calls]

    def __call__(self, argv, **kw):
        argv = list(argv)
        self.calls.append(argv)
        self.last_kwargs = kw
        if self.on_call is not None:
            self.on_call(argv)
        if argv[:3] == ["gh", "pr", "list"]:
            assert argv == sc.open_prs_argv(_FIELDS)
            if self.list_mode == "ok":
                return _proc(0, json.dumps(_graphql_rows(self.pulls[:sc.OPEN_PRS_LIMIT])))
            if self.list_mode == "refused":
                return _proc(1, "", _LIST_REFUSED_STDERR)
            return _proc(1, "", self.list_stderr)
        if argv[:3] == ["gh", "repo", "view"]:
            if self.list_mode == "ok":
                return _proc(0, json.dumps({"nameWithOwner": "zwrose/superheroes"}))
            return _proc(1, "", _REPO_VIEW_REFUSED_STDERR)
        if argv == ["gh", "api", "repos/{owner}/{repo}"]:
            return _proc(0, _REPOS_JSON)
        assert argv[:2] == ["gh", "api"] and len(argv) == 3, argv
        m = _PAGE_RE.match(argv[2])
        assert m, argv
        n = int(m.group(1))
        if n in self.fail_pages:
            return _proc(1, "", "gh: Bad gateway (HTTP 502)")
        if n in self.junk_pages:
            return _proc(0, "<html>not json")
        if n in self.object_pages:
            return _proc(0, json.dumps({"message": "not a list"}))
        return _proc(0, json.dumps(self.pulls[(n - 1) * 100:n * 100]))


@pytest.fixture(autouse=True)
def _gh_on_path(monkeypatch):
    monkeypatch.setattr(sc.shutil, "which", lambda name: "/usr/bin/gh" if name == "gh" else None)


def _list(gh, **kw):
    return sc.list_open_prs(_FIELDS, run=gh, timeout=30, run_kwargs={"cwd": "/repo", "env": {"A": "1"}}, **kw)


def _lookup(gh, base_sha):
    return L._lookup_stack_entry_pr("/repo", base_sha, gh_run=gh)


# ---- equivalence (DoD row 1) ----

def test_the_fixture_is_three_open_prs():
    assert [p["number"] for p in _PULLS_PAGE1] == [2113, 2111, 2029]
    assert "HTTP 403" in _LIST_REFUSED_STDERR and "use the REST API" in _LIST_REFUSED_STDERR


def test_both_transports_return_the_same_rows():
    graphql = FakeGh(_PULLS_PAGE1, list_mode="ok")
    rest = FakeGh(_PULLS_PAGE1, list_mode="refused")
    graphql_rows, graphql_refusal = _list(graphql)
    rest_rows, rest_refusal = _list(rest)
    assert graphql_refusal is None and rest_refusal is None
    assert rest_rows == graphql_rows == _graphql_rows(_PULLS_PAGE1)
    assert rest.pages_asked == [1]


def test_the_launcher_resolves_the_same_entry_pr_on_both_transports():
    base = _PULLS_PAGE1[1]["head"]["sha"]
    graphql = _lookup(FakeGh(_PULLS_PAGE1, list_mode="ok"), base)
    rest_gh = FakeGh(_PULLS_PAGE1, list_mode="refused")
    rest = _lookup(rest_gh, base)
    assert graphql == rest == {"ok": True, "pr": 2111, "repo": "zwrose/superheroes"}
    assert rest_gh.pages_asked == [1]


# ---- E1 / E2 / E3: which transport answers ----

def test_e1_graphql_success_makes_no_rest_call():
    gh = FakeGh(_PULLS_PAGE1, list_mode="ok")
    rows, refusal = _list(gh)
    assert refusal is None and rows == _graphql_rows(_PULLS_PAGE1)
    assert gh.rest_calls == [] and len(gh.calls) == 1


@pytest.mark.parametrize("stderr", [
    "HTTP 401: Bad credentials (https://api.github.com/graphql)",
    "HTTP 403: API rate limit exceeded",
    "GitHub GraphQL is not available; use the REST API",
    "gh: something broke",
    "",
])
def test_e2_a_graphql_failure_that_is_not_the_proxy_refusal_makes_no_rest_call(stderr):
    gh = FakeGh(_PULLS_PAGE1, list_mode="error", list_stderr=stderr)
    rows, refusal = _list(gh)
    assert rows is None
    assert refusal["reason"] == sc.REASON_STACK_UNREADABLE
    assert not refusal["detail"].startswith("graphql refused")
    assert gh.rest_calls == [] and len(gh.calls) == 1


@pytest.mark.parametrize("raised", [OSError("no gh"), FileNotFoundError("gh"), subprocess.TimeoutExpired("gh", 1)])
def test_e2_a_graphql_run_that_raises_is_a_refusal_without_a_rest_call(raised):
    calls = []

    def run(argv, **kw):
        calls.append(argv)
        raise raised

    rows, refusal = sc.list_open_prs(_FIELDS, run=run, timeout=30)
    assert rows is None and refusal["reason"] == sc.REASON_STACK_UNREADABLE
    assert len(calls) == 1


@pytest.mark.parametrize("stdout", ["not json", "", json.dumps({"a": 1}), json.dumps([1, 2]), json.dumps([{"number": 1}, "x"])])
def test_e2_a_graphql_body_that_is_not_a_list_of_objects_is_a_refusal(stdout):
    rows, refusal = sc.list_open_prs(_FIELDS, run=lambda argv, **kw: _proc(0, stdout), timeout=30)
    assert rows is None and refusal["reason"] == sc.REASON_STACK_UNREADABLE


def test_e3_the_recorded_proxy_refusal_reads_rest_with_the_same_cwd_and_env():
    gh = FakeGh(_PULLS_PAGE1, list_mode="refused")
    rows, refusal = _list(gh)
    assert refusal is None and rows == _graphql_rows(_PULLS_PAGE1)
    assert gh.rest_calls == [["gh", "api", _PULLS_PATH + "&per_page=100&page=1"]]
    assert gh.last_kwargs["cwd"] == "/repo" and gh.last_kwargs["env"] == {"A": "1"}


def test_only_the_requested_fields_are_emitted():
    gh = FakeGh(_PULLS_PAGE1, list_mode="refused")
    rows, refusal = sc.list_open_prs(("number",), run=lambda argv, **kw: (
        _proc(1, "", _LIST_REFUSED_STDERR) if argv[:3] == ["gh", "pr", "list"] else gh(argv, **kw)), timeout=30)
    assert refusal is None and rows == [{"number": 2113}, {"number": 2111}, {"number": 2029}]


def test_fields_outside_the_three_are_a_programming_error():
    for bad in [("number", "title"), (), "number", ("body",)]:
        with pytest.raises(ValueError):
            sc.list_open_prs(bad, run=FakeGh([]), timeout=30)


def test_the_argv_and_the_limit():
    assert sc.OPEN_PRS_LIMIT == 1000
    assert sc.open_prs_argv(("number", "headRefOid", "state")) == [
        "gh", "pr", "list", "--state", "open", "--json", "number,headRefOid,state", "--limit", "1000"]


# ---- E4 / E5 / E6: a failed REST read is a refusal, never rows ----

def test_e4_a_rest_page_that_exits_non_zero_after_the_refusal_is_a_prefixed_refusal():
    gh = FakeGh(_PULLS_PAGE1, fail_pages=(1,))
    rows, refusal = _list(gh)
    assert rows is None
    assert refusal["reason"] == sc.REASON_STACK_UNREADABLE
    assert refusal["detail"].startswith("graphql refused; rest: gh api ")
    assert "HTTP 502" in refusal["detail"] and "page=1" in refusal["detail"]


def test_e4_a_later_page_that_fails_loses_the_earlier_pages_rows():
    gh = FakeGh([_pull(n) for n in range(1, 151)], fail_pages=(2,))
    rows, refusal = _list(gh)
    assert rows is None and "page=2" in refusal["detail"]
    assert refusal["detail"].startswith("graphql refused; rest: ")


@pytest.mark.parametrize("raised", [OSError("boom"), subprocess.TimeoutExpired("gh", 1)])
def test_e4_a_rest_run_that_raises_is_a_prefixed_refusal(raised):
    def run(argv, **kw):
        if argv[:3] == ["gh", "pr", "list"]:
            return _proc(1, "", _LIST_REFUSED_STDERR)
        raise raised

    rows, refusal = sc.list_open_prs(_FIELDS, run=run, timeout=30)
    assert rows is None and refusal["detail"].startswith("graphql refused; rest: gh api ")


@pytest.mark.parametrize("kind", ["junk_pages", "object_pages"])
def test_e5_a_rest_page_that_is_not_a_json_list_is_a_refusal(kind):
    gh = FakeGh(_PULLS_PAGE1, **{kind: (1,)})
    rows, refusal = _list(gh)
    assert rows is None and refusal["detail"].startswith("graphql refused; rest: ")
    assert ("not JSON" in refusal["detail"]) if kind == "junk_pages" else ("not a list" in refusal["detail"])


def _bad_rows():
    good = _pull(7)
    no_sha = {"number": 7, "state": "open", "head": {}}
    no_head = {"number": 7, "state": "open"}
    sha_int = {"number": 7, "state": "open", "head": {"sha": 5}}
    bool_number = {"number": True, "state": "open", "head": {"sha": _sha(7)}}
    str_number = {"number": "7", "state": "open", "head": {"sha": _sha(7)}}
    closed = {"number": 7, "state": "closed", "head": {"sha": _sha(7)}}
    no_state = {"number": 7, "head": {"sha": _sha(7)}}
    return [no_sha, no_head, sha_int, bool_number, str_number, closed, no_state, "row", None]


@pytest.mark.parametrize("bad", _bad_rows(), ids=lambda b: json.dumps(b)[:60])
def test_e6_one_malformed_row_refuses_the_whole_read(bad):
    gh = FakeGh([_pull(8), bad, _pull(9)])
    rows, refusal = _list(gh)
    assert rows is None and refusal["reason"] == sc.REASON_STACK_UNREADABLE
    assert refusal["detail"].startswith("graphql refused; rest: ")


# ---- E7: a spent budget refuses, it never raises ----

def _clock(monkeypatch, start=0.0):
    clock = [start]
    monkeypatch.setattr(sc, "time", SimpleNamespace(monotonic=lambda: clock[0]))
    return clock


def test_e7_a_budget_spent_by_the_refusal_stops_the_read_before_the_first_rest_page(monkeypatch):
    clock = _clock(monkeypatch)

    def spend(argv):
        if argv[:3] == ["gh", "pr", "list"]:
            clock[0] = 101.0

    gh = FakeGh(_PULLS_PAGE1, on_call=spend)
    rows, refusal = _list(gh, deadline_at=100.0)
    assert rows is None
    assert refusal["detail"] == "graphql refused; rest: read budget exhausted after 0 pages"
    assert gh.rest_calls == []


def test_e7_a_budget_spent_between_pages_stops_the_read_there(monkeypatch):
    clock = _clock(monkeypatch)

    def spend(argv):
        if argv[:2] == ["gh", "api"] and argv[2].endswith("page=1"):
            clock[0] = 101.0

    gh = FakeGh([_pull(n) for n in range(1, 151)], on_call=spend)
    rows, refusal = _list(gh, deadline_at=100.0)
    assert rows is None and "read budget exhausted" in refusal["detail"]
    assert gh.pages_asked == [1]


def test_e7_the_budget_message_names_the_duration_only_when_there_is_one(monkeypatch):
    _clock(monkeypatch, start=5.0)
    argv = ["gh", "api", "repos/x/y/pulls/1"]
    _, refusal = sc._transport_rest(argv, 30, FakeGh([]), None, None, 2, deadline_at=1.0)
    assert refusal["reason"] == sc.REASON_STACK_UNREADABLE
    assert refusal["detail"] == "read budget exhausted after 2 pages"
    _, refusal = sc._transport_rest(argv, 30, FakeGh([]), None, None, 2, deadline=3, deadline_at=1.0)
    assert refusal["detail"] == "read budget of 3 seconds exhausted after 2 pages"


def test_transport_rest_reads_a_list_only_when_asked():
    payload = SimpleNamespace(returncode=0, stdout="[1, 2]", stderr="")
    got, refusal = sc._transport_rest(["gh", "api", "e"], 30, lambda a, **k: payload, None, None, 0, expect_list=True)
    assert got == [1, 2] and refusal is None
    got, refusal = sc._transport_rest(["gh", "api", "e"], 30, lambda a, **k: payload, None, None, 0)
    assert got is None and "not an object" in refusal["detail"]
    obj = SimpleNamespace(returncode=0, stdout="{}", stderr="")
    got, refusal = sc._transport_rest(["gh", "api", "e"], 30, lambda a, **k: obj, None, None, 0, expect_list=True)
    assert got is None and "returned JSON that is not a list" in refusal["detail"]


# ---- E8: the limit ----

def _many(count):
    return [_pull(10000 - i) for i in range(count)]


def test_e8_1001_open_prs_read_exactly_the_first_1000_and_never_ask_for_page_11():
    pulls = _many(1001)
    gh = FakeGh(pulls)
    rows, refusal = _list(gh)
    assert refusal is None
    assert rows == _graphql_rows(pulls[:1000])
    assert gh.pages_asked == list(range(1, 11))


def test_e8_a_matching_head_at_row_1001_is_not_seen_by_the_launcher():
    pulls = _many(1001)
    result = _lookup(FakeGh(pulls), pulls[1000]["head"]["sha"])
    assert result == {"ok": False, "reason": "base-not-layer-head"}


def test_e8_a_matching_head_at_row_1000_is_seen_by_the_launcher():
    pulls = _many(1001)
    result = _lookup(FakeGh(pulls), pulls[999]["head"]["sha"])
    assert result == {"ok": True, "pr": pulls[999]["number"], "repo": "zwrose/superheroes"}


def test_e8_two_matches_split_across_the_boundary_are_one_candidate():
    pulls = _many(1001)
    shared = _sha(424242)
    pulls[999]["head"]["sha"] = shared
    pulls[1000]["head"]["sha"] = shared
    result = _lookup(FakeGh(pulls), shared)
    assert result == {"ok": True, "pr": pulls[999]["number"], "repo": "zwrose/superheroes"}


# ---- E9: the launcher keeps a refusal a refusal ----

def test_e9_a_rest_refusal_after_the_graphql_refusal_is_stack_read_unavailable_not_base_not_layer_head():
    base = _PULLS_PAGE1[0]["head"]["sha"]
    result = _lookup(FakeGh(_PULLS_PAGE1, fail_pages=(1,)), base)
    assert result["ok"] is False and result["reason"] == "stack-read-unavailable"
    assert result["detail"].startswith("graphql refused; rest: gh api ")


def test_e9_a_graphql_failure_that_is_not_the_refusal_is_stack_read_unavailable():
    gh = FakeGh(_PULLS_PAGE1, list_mode="ok")
    real = gh.__call__

    def run(argv, **kw):
        if argv[:3] == ["gh", "pr", "list"]:
            return _proc(1, "", "HTTP 401: Bad credentials")
        return real(argv, **kw)

    result = L._lookup_stack_entry_pr("/repo", _PULLS_PAGE1[0]["head"]["sha"], gh_run=run)
    assert result["ok"] is False and result["reason"] == "stack-read-unavailable"
    assert "401" in result["detail"]


def test_e9_the_absolute_deadline_reaches_the_seam(monkeypatch):
    seen = {}
    real = sc.list_open_prs

    def spy(fields, **kw):
        seen.update(kw)
        return real(fields, **kw)

    monkeypatch.setattr(sc, "list_open_prs", spy)
    deadline = L.time.monotonic() + 500
    result = L._lookup_stack_entry_pr(
        "/repo", _PULLS_PAGE1[0]["head"]["sha"], gh_run=FakeGh(_PULLS_PAGE1, list_mode="ok"), deadline=deadline)
    assert result["ok"] is True
    assert seen["deadline_at"] == deadline and seen["run_kwargs"]["cwd"] == "/repo"


# ---- E10: gh_pages.read limit ----

def _page_fetch(rows, asked):
    def fetch(endpoint):
        n = int(re.search(r"page=(\d+)$", endpoint).group(1))
        asked.append(n)
        return json.dumps(rows[(n - 1) * 100:n * 100])
    return fetch


def test_e10_without_a_limit_every_page_is_read():
    asked = []
    rows = gh_pages.read(_page_fetch(list(range(250)), asked), "repos/o/r/pulls")
    assert rows == list(range(250)) and asked == [1, 2, 3]


def test_e10_a_limit_stops_the_read_and_returns_exactly_that_many_rows():
    asked = []
    rows = gh_pages.read(_page_fetch(list(range(250)), asked), "repos/o/r/pulls", limit=150)
    assert rows == list(range(150)) and asked == [1, 2]


def test_e10_a_limit_met_by_a_full_page_asks_for_no_later_page():
    asked = []
    rows = gh_pages.read(_page_fetch(list(range(250)), asked), "repos/o/r/pulls", limit=100)
    assert rows == list(range(100)) and asked == [1]


def test_e10_a_limit_above_the_list_returns_the_whole_list():
    asked = []
    rows = gh_pages.read(_page_fetch(list(range(120)), asked), "repos/o/r/pulls", limit=500)
    assert rows == list(range(120)) and asked == [1, 2]


def test_e10_a_page_that_fails_before_the_limit_is_reached_fails_the_whole_read():
    def fetch(endpoint):
        return json.dumps(list(range(100))) if endpoint.endswith("page=1") else None

    assert gh_pages.read(fetch, "repos/o/r/pulls", limit=150) is None


def test_e10_a_non_list_page_before_the_limit_is_reached_fails_the_whole_read():
    def fetch(endpoint):
        return json.dumps(list(range(100))) if endpoint.endswith("page=1") else json.dumps({"a": 1})

    assert gh_pages.read(fetch, "repos/o/r/pulls", limit=150) is None


# ---- the closing-keyword regex has one home ----

def test_the_closing_keyword_regex_has_one_home():
    assert review_record._CLOSES_RE is sc.CLOSES_RE
    assert sc.CLOSES_RE.pattern.startswith(sc.CLOSING_KEYWORD)
    assert wave_watch._CLOSING_REF_RE.pattern.startswith(sc.CLOSING_KEYWORD)
    for body in ("Fixes #17", "closed: o/r#3", "RESOLVE #9"):
        assert sc.CLOSES_RE.search(body)
        assert wave_watch._CLOSING_REF_RE.search(body)
    assert not sc.CLOSES_RE.search("prefix #17")
    assert sc.CLOSES_RE.flags & __import__("re").IGNORECASE
