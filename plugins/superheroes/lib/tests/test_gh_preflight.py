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
