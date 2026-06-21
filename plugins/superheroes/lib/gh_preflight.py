"""GitHub-access preflight — a fail-CLOSED entry gate for workhorse (and future
consumers like the showrunner #22). Mirrors the band's pure-decide + best-effort
probe + JSON CLI shape (freshness.decide / detect.py / repo_doctor.py). Judges
GitHub's EFFECTIVE access for the repo (token-type-agnostic), never scope labels.
Read-only; never prints or persists the token.
"""
import json
import shutil
import subprocess
import sys

# required-access level -> the effective-permission key that must be True.
_CAPABILITY = {"write": "push", "read": "pull"}

# Where the operator's access requirements are documented (FR-4); failure
# messages point here.
DOC = "plugins/superheroes/skills/workhorse/reference/github-access.md"

# One-line human description per cause.
_CAUSE_TEXT = {
    "gh_missing": "the GitHub CLI `gh` is not installed",
    "not_authenticated": "`gh` is not signed in to an active GitHub account",
    "no_remote": "this repository has no GitHub remote configured",
    "no_access": "the active GitHub account lacks the required access to this repository",
    "indeterminate": "GitHub access could not be determined",
}


def _remediation(cause, required):
    """The exact next command that resolves `cause` (FR-3)."""
    if cause == "gh_missing":
        return "install gh — see https://cli.github.com"
    if cause == "not_authenticated":
        return "gh auth login -s repo"
    if cause == "no_remote":
        return "git remote add origin <url>"
    if cause == "no_access":
        return ("gh auth refresh -s repo  (or `gh auth switch` to an account with "
                "%s access)" % required)
    return "verify GitHub is reachable and retry"


def decide(probe, required="write"):
    """(ok: bool, cause: str|None, remediation: str|None).

    Pure + fail-CLOSED. The check order matches probe()'s short-circuit order, with
    `error` taking precedence so a failed/timed-out read reads as indeterminate
    (never misread as 'not signed in').
    """
    cap = _CAPABILITY.get(required) if isinstance(required, str) else None
    if cap is None:
        return (False, "indeterminate", _remediation("indeterminate", required))
    if not isinstance(probe, dict):
        return (False, "indeterminate", _remediation("indeterminate", required))
    if probe.get("gh_installed") is not True:
        return (False, "gh_missing", _remediation("gh_missing", required))
    if probe.get("error"):
        return (False, "indeterminate", _remediation("indeterminate", required))
    if probe.get("authenticated") is not True:
        return (False, "not_authenticated", _remediation("not_authenticated", required))
    if probe.get("remote_configured") is not True:
        return (False, "no_remote", _remediation("no_remote", required))
    perms = probe.get("permissions")
    if not isinstance(perms, dict):
        return (False, "indeterminate", _remediation("indeterminate", required))
    if perms.get(cap) is True:
        return (True, None, None)
    return (False, "no_access", _remediation("no_access", required))


def message(probe, ok, cause, remediation):
    """A one-line operator-facing message: cause, account/repo where known, the exact
    fix, the doc pointer, and (for indeterminate) the underlying error (UFR-4)."""
    if ok:
        return "GitHub access OK"
    parts = [_CAUSE_TEXT.get(cause, _CAUSE_TEXT["indeterminate"])]
    acct = probe.get("account") if isinstance(probe, dict) else None
    repo = probe.get("repo") if isinstance(probe, dict) else None
    if cause == "no_access" and (acct or repo):
        parts.append("account %s, repo %s" % (acct or "?", repo or "?"))
    if cause == "indeterminate" and isinstance(probe, dict) and probe.get("error"):
        parts.append("(%s)" % str(probe["error"]).strip())
    parts.append("Fix: %s" % remediation)
    parts.append("See %s" % DOC)
    return " — ".join(parts)
