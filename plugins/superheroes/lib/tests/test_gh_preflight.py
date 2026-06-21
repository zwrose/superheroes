import json
import subprocess

import gh_preflight


# ---- decide(): the spec cases ----

def _ok_probe(push=True, pull=True):
    return {"gh_installed": True, "authenticated": True, "remote_configured": True,
            "account": "alice", "repo": "alice/repo",
            "permissions": {"push": push, "pull": pull}, "error": None}


def test_decide_write_present_passes():
    ok, cause, rem = gh_preflight.decide(_ok_probe(), required="write")
    assert ok is True and cause is None and rem is None


def test_decide_write_absent_is_no_access():
    ok, cause, _ = gh_preflight.decide(_ok_probe(push=False), required="write")
    assert ok is False and cause == "no_access"


def test_decide_read_only_required_passes_on_pull():
    ok, cause, _ = gh_preflight.decide(_ok_probe(push=False, pull=True), required="read")
    assert ok is True and cause is None


def test_decide_gh_missing():
    ok, cause, _ = gh_preflight.decide({"gh_installed": False}, required="write")
    assert ok is False and cause == "gh_missing"


def test_decide_not_authenticated():
    probe = {"gh_installed": True, "authenticated": False, "error": None}
    ok, cause, _ = gh_preflight.decide(probe, required="write")
    assert ok is False and cause == "not_authenticated"


def test_decide_no_remote():
    probe = {"gh_installed": True, "authenticated": True, "remote_configured": False,
             "error": None}
    ok, cause, _ = gh_preflight.decide(probe, required="write")
    assert ok is False and cause == "no_remote"


def test_decide_indeterminate_on_error():
    probe = {"gh_installed": True, "authenticated": True, "remote_configured": True,
             "permissions": None, "error": "HTTP 503 from api.github.com"}
    ok, cause, _ = gh_preflight.decide(probe, required="write")
    assert ok is False and cause == "indeterminate"


def test_decide_error_takes_precedence_over_auth():
    # an auth-stage timeout leaves authenticated False AND sets error — must read as
    # indeterminate (surface the timeout), never as 'not_authenticated'.
    probe = {"gh_installed": True, "authenticated": False,
             "error": "TimeoutExpired: gh auth status"}
    _, cause, _ = gh_preflight.decide(probe, required="write")
    assert cause == "indeterminate"


def test_decide_malformed_probe_fails_closed():
    assert gh_preflight.decide(None)[:2] == (False, "indeterminate")
    assert gh_preflight.decide("nope")[:2] == (False, "indeterminate")
    weird = {"gh_installed": True, "authenticated": True, "remote_configured": True,
             "permissions": "weird", "error": None}
    assert gh_preflight.decide(weird)[1] == "indeterminate"


def test_decide_unknown_required_level_fails_closed():
    ok, cause, _ = gh_preflight.decide(_ok_probe(), required="admin")
    assert ok is False and cause == "indeterminate"


def test_decide_push_must_be_exactly_true():
    # a truthy non-bool must not pass (fail-closed bool guard).
    probe = {"gh_installed": True, "authenticated": True, "remote_configured": True,
             "permissions": {"push": "yes"}, "error": None}
    assert gh_preflight.decide(probe, required="write")[0] is False


# ---- message(): operator-facing rendering ----

def test_message_pass_is_ok():
    assert "OK" in gh_preflight.message(_ok_probe(), True, None, None)


def test_message_fail_names_fix_and_doc_pointer():
    ok, cause, rem = gh_preflight.decide({"gh_installed": False})
    msg = gh_preflight.message({"gh_installed": False}, ok, cause, rem)
    assert rem in msg and gh_preflight.DOC in msg


def test_message_indeterminate_surfaces_underlying_error():
    probe = {"gh_installed": True, "authenticated": True, "remote_configured": True,
             "permissions": None, "error": "HTTP 503 from api.github.com"}
    ok, cause, rem = gh_preflight.decide(probe)
    msg = gh_preflight.message(probe, ok, cause, rem)
    assert "HTTP 503" in msg  # UFR-4: the underlying error is surfaced


# ---- probe(): injected-runner world-reads ----

class FakeProc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def make_run(responses):
    """responses: {substring-of-command: FakeProc | Exception}. First match wins;
    an Exception value is raised (to test the never-raises guard)."""
    def run(args, **kwargs):
        joined = " ".join(args)
        for key, resp in responses.items():
            if key in joined:
                if isinstance(resp, Exception):
                    raise resp
                return resp
        return FakeProc(returncode=0, stdout="", stderr="")
    return run


_AUTHED = {
    "auth status": FakeProc(0),
    "api user": FakeProc(0, stdout="alice\n"),
    "remote get-url": FakeProc(0, stdout="git@github.com:alice/repo.git\n"),
    "repo view": FakeProc(0, stdout="alice/repo\n"),
}


def test_probe_gh_missing(monkeypatch):
    monkeypatch.setattr(gh_preflight.shutil, "which", lambda _name: None)
    p = gh_preflight.probe(".", run=make_run({}))
    assert p["gh_installed"] is False


def test_probe_not_authenticated(monkeypatch):
    monkeypatch.setattr(gh_preflight.shutil, "which", lambda _name: "/usr/bin/gh")
    p = gh_preflight.probe(".", run=make_run({"auth status": FakeProc(1, stderr="no")}))
    assert p["gh_installed"] is True and p["authenticated"] is False


def test_probe_no_remote(monkeypatch):
    monkeypatch.setattr(gh_preflight.shutil, "which", lambda _name: "/usr/bin/gh")
    resp = dict(_AUTHED)
    resp["remote get-url"] = FakeProc(2, stderr="No such remote 'origin'")
    p = gh_preflight.probe(".", run=make_run(resp))
    assert p["authenticated"] is True and p["remote_configured"] is False


def test_probe_write_present(monkeypatch):
    monkeypatch.setattr(gh_preflight.shutil, "which", lambda _name: "/usr/bin/gh")
    resp = dict(_AUTHED)
    resp["api repos/"] = FakeProc(0, stdout='{"push": true, "pull": true}')
    p = gh_preflight.probe(".", run=make_run(resp))
    assert p["repo"] == "alice/repo"
    assert p["permissions"] == {"push": True, "pull": True}
    assert gh_preflight.decide(p, required="write")[0] is True


def test_probe_permissions_error_sets_error(monkeypatch):
    monkeypatch.setattr(gh_preflight.shutil, "which", lambda _name: "/usr/bin/gh")
    resp = dict(_AUTHED)
    resp["api repos/"] = FakeProc(1, stderr="HTTP 404: Not Found")
    p = gh_preflight.probe(".", run=make_run(resp))
    assert p["permissions"] is None and "404" in p["error"]


def test_probe_repo_view_error_sets_error(monkeypatch):
    # the repo-view stop-point: a failed `gh repo view` (404 / no access) sets error
    # and short-circuits before the permissions read -> indeterminate (fail-closed).
    monkeypatch.setattr(gh_preflight.shutil, "which", lambda _name: "/usr/bin/gh")
    resp = dict(_AUTHED)
    resp["repo view"] = FakeProc(1, stderr="HTTP 404: Not Found")
    p = gh_preflight.probe(".", run=make_run(resp))
    assert p["repo"] is None and p["error"] is not None
    assert gh_preflight.decide(p)[1] == "indeterminate"


def test_probe_never_raises_on_exception(monkeypatch):
    # the UFR-4 path: an exception-throwing runner must yield a structured error.
    monkeypatch.setattr(gh_preflight.shutil, "which", lambda _name: "/usr/bin/gh")
    boom = subprocess.TimeoutExpired(cmd="gh auth status", timeout=10)
    p = gh_preflight.probe(".", run=make_run({"auth status": boom}))  # must not raise
    assert p["error"] is not None
    assert gh_preflight.decide(p)[1] == "indeterminate"
