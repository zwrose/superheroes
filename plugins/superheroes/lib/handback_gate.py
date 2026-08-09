#!/usr/bin/env python3
"""Handback gate — parser, subject resolver, semantic validator, scope markers (#624 §4).

Refuses ``gh pr ready`` / non-draft ``gh pr create`` in a mechanically-marked full-lane worktree
that lacks an allowlisted review receipt. This class is a **Claude-host, Bash-tool, honest-agent
tripwire**. It does not cover aliases, wrapper scripts, non-Bash tools, or other hosts. **It is
not a security boundary and is not claimed as one.**

**``gh pr ready`` residual:** for a bare ``gh pr ready`` with no selector, binding is branch +
HEAD — the PR's remote base cannot be resolved without a network call inside a deterministic hook.
That residual is covered by the advisor vet's existing remote-head duty. An explicit selector is a
different case and refuses ``handback-subject-unresolvable``.
"""
import hashlib
import json
import os
import re
import subprocess

import round_driver as RD
import round_records as RR
import store_core
from worktree_guard import _split_segments, _tokenize_segment, _strip_shell_prefixes

SCHEMA = "handback-decision/1"
BUILD_LANE_FILE = "build-lane.json"
REVIEW_SESSION_FILE = "review-session.json"
HANDBACK_VERDICT_ALLOWLIST = ("converged", "uncertified-manual")

BUILD_LANE_SCHEMA = "build-lane/1"
REVIEW_SESSION_SCHEMA = "review-session/1"

_SIDECAR_DIR = RD.SIDECAR_DIRNAME
_SIDECAR_FILE = RD.SIDECAR_FILE

_REFUSAL_DETAIL = (
    "superheroes review-receipt gate: no valid full-lane review receipt for HEAD %s — "
    "finish the review to a certified terminal, or attest (`round_driver.py attest`); "
    "if genuinely stuck, park to the advisor."
)

_PR_URL = re.compile(
    r"^(?P<base>[a-zA-Z][a-zA-Z0-9+.\-]*://[^/]+/[^/]+/[^/]+)/pull/(?P<num>\d+)(?:[/?#].*)?$"
)
_GH_REPO_SLUG = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")

_ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_GH_PR_OPTS = {
    "-R": True, "--repo": True,
    "-H": True, "--head": True,
    "-B": True, "--base": True,
    "-d": False, "--draft": False,
    "--undo": False,
}


def _is_gh_token(token):
    base = os.path.basename(token)
    return base == "gh" or base == "gh.exe"


def _expand_clustered_flags(token, option_specs):
    """Minimal clustered-short-flag expander for gh pr flags."""
    if not token.startswith("-") or token.startswith("--"):
        if token.startswith("--"):
            base = token.split("=", 1)[0]
            expects = option_specs.get(base, False) if "=" not in token else False
            return ([token], None, expects)
        return ([token], None, False)
    letters = token[1:]
    if not letters or not letters.isalpha():
        return ([token], None, False)
    flags = []
    i = 0
    while i < len(letters):
        c = letters[i]
        opt = "-%s" % c
        flags.append(opt)
        if opt in option_specs and option_specs[opt]:
            rest = letters[i + 1:]
            if rest:
                return (flags, rest, False)
            return (flags, None, True)
        i += 1
    return (flags, None, False)


def _option_value(tokens, idx):
    tok = tokens[idx]
    if "=" in tok:
        return tok.split("=", 1)[1], 0
    if idx + 1 < len(tokens):
        return tokens[idx + 1], 1
    return None, 1


def _capture_env_prefix(tokens):
    """Capture leading VAR=value assignments (gh-specific — do not discard)."""
    env = {}
    start = 0
    while start < len(tokens) and "=" in tokens[start] and not tokens[start].startswith("="):
        key = tokens[start].split("=", 1)[0]
        if _ENV_ASSIGN_RE.match(key):
            k, v = tokens[start].split("=", 1)
            env[k] = v
            start += 1
            continue
        break
    return env, tokens[start:]


def _parse_pr_args(args):
    """Parse flags and operands for ``gh pr ready`` / ``gh pr create``."""
    repo = head = base = None
    selector = None
    draft = undo = False
    parse_error = False
    operands = []
    i = 0
    while i < len(args):
        tok = args[i]
        if tok == "--":
            operands.extend(args[i + 1:])
            break
        if not tok.startswith("-"):
            operands.append(tok)
            i += 1
            continue
        flags, inline, expects = _expand_clustered_flags(tok, _GH_PR_OPTS)
        for part in flags:
            base_flag = part.split("=", 1)[0]
            if base_flag in ("-d", "--draft"):
                draft = True
            elif base_flag == "--undo":
                undo = True
            elif base_flag in ("-R", "--repo"):
                val = inline
                consumed = 0
                if val is None:
                    val, consumed = _option_value(args, i)
                if val is None:
                    parse_error = True
                else:
                    repo = val
                i += 1 + consumed
                break
            elif base_flag in ("-H", "--head"):
                val = inline
                consumed = 0
                if val is None:
                    val, consumed = _option_value(args, i)
                if val is None:
                    parse_error = True
                else:
                    head = val
                i += 1 + consumed
                break
            elif base_flag in ("-B", "--base"):
                val = inline
                consumed = 0
                if val is None:
                    val, consumed = _option_value(args, i)
                if val is None:
                    parse_error = True
                else:
                    base = val
                i += 1 + consumed
                break
            else:
                i += 1
        else:
            if expects:
                if i + 1 >= len(args):
                    parse_error = True
                i += 2
            else:
                i += 1
    if operands and selector is None:
        selector = operands[0]
    return {
        "repo": repo,
        "head": head,
        "base": base,
        "selector": selector,
        "draft": draft,
        "undo": undo,
        "parse_error": parse_error,
    }


def _classify_gh(tokens, segment_text):
    """Classify one tokenized gh invocation."""
    if not tokens or not _is_gh_token(tokens[0]):
        return None
    rest = tokens[1:]
    if len(rest) >= 2 and rest[0] == "api" and rest[1] == "graphql":
        if "markPullRequestReadyForReview" in segment_text:
            return {"action": "graphql-ready", "argv": tokens, "draft": False, "undo": False,
                    "parse_error": False, "pr": {}}
        return None
    if len(rest) >= 2 and rest[0] == "pr":
        sub = rest[1]
        pr_args = rest[2:]
        parsed = _parse_pr_args(pr_args)
        if sub == "ready":
            if parsed["undo"]:
                return {"action": "pr-ready", "argv": tokens, "draft": False, "undo": True,
                        "parse_error": parsed["parse_error"], "pr": parsed}
            return {"action": "pr-ready", "argv": tokens, "draft": False, "undo": False,
                    "parse_error": parsed["parse_error"], "pr": parsed}
        if sub == "create":
            if parsed["draft"]:
                return {"action": "pr-create", "argv": tokens, "draft": True, "undo": False,
                        "parse_error": parsed["parse_error"], "pr": parsed}
            return {"action": "pr-create", "argv": tokens, "draft": False, "undo": False,
                    "parse_error": parsed["parse_error"], "pr": parsed}
    return None


def parse_gh_invocations(command):
    """Parse bash command text for guarded ``gh`` invocations."""
    if not isinstance(command, str):
        return []
    invocations = []
    for segment in _split_segments(command):
        tokens = _tokenize_segment(segment)
        if not tokens:
            continue
        inline_env, tokens = _capture_env_prefix(tokens)
        tokens = _strip_shell_prefixes(tokens)
        if not tokens or not _is_gh_token(tokens[0]):
            continue
        classified = _classify_gh(tokens, segment)
        if classified is None:
            continue
        inv = {
            "action": classified["action"],
            "argv": classified["argv"],
            "env": {},
            "undo": classified["undo"],
            "draft": classified["draft"],
            "parse_error": classified.get("parse_error", False),
            "pr": classified.get("pr", {}),
        }
        for key in ("GH_REPO", "GH_HOST"):
            if key in inline_env:
                inv["env"][key] = inline_env[key]
        invocations.append(inv)
    return invocations


def _normalize_repo_arg(value):
    if not value:
        return None
    m = _PR_URL.match(value)
    if m:
        return store_core.normalize_remote(m.group("base"))
    if _GH_REPO_SLUG.match(value):
        host = "github.com"
        return "%s/%s" % (host, value)
    return store_core.normalize_remote(value)


def command_subject(invocation, environ=None):
    """Resolve repo/selector/head/base from one parsed gh invocation."""
    environ = environ if environ is not None else os.environ
    pr = invocation.get("pr") or {}
    repo = pr.get("repo")
    repo_source = None
    if repo:
        repo_source = "flag"
        repo = _normalize_repo_arg(repo)
    selector = pr.get("selector")
    head = pr.get("head")
    base = pr.get("base")
    for operand in _pr_url_operands(invocation):
        if selector is None:
            selector = operand
        parsed = _normalize_repo_arg(operand)
        if parsed and repo is None:
            repo = parsed
            repo_source = "url"
    inline = invocation.get("env") or {}
    if repo is None and inline.get("GH_REPO"):
        repo = _normalize_repo_arg(inline["GH_REPO"])
        repo_source = "env-inline"
    if repo is None and environ.get("GH_REPO"):
        repo = _normalize_repo_arg(environ["GH_REPO"])
        repo_source = "env-inherited"
    return {
        "repo": repo,
        "selector": selector,
        "head": head,
        "base": base,
        "repoSource": repo_source,
    }


def _pr_url_operands(invocation):
    """Yield operand tokens that look like PR URLs."""
    argv = invocation.get("argv") or []
    for tok in argv[1:]:
        if _PR_URL.match(tok):
            yield tok


def _worktree_toplevel(repo_root, run_git):
    """Repo root via store_core, the one sanctioned resolver (`test_repo_root_census`).

    `run_git` stays in the signature as the injected-seam marker for callers, but resolution
    itself must not hand-roll `rev-parse --show-toplevel` — the census forbids it outside
    store_core, and a second resolver is exactly the drift that check exists to stop. An
    unresolvable root returns None, which `_marker_repo_matches` already reads as "not this
    worktree" — the fail-closed direction for a scope marker.
    """
    try:
        return store_core.repo_root(repo_root)
    except store_core.RepoRootUnavailable:
        return None


def _marker_repo_matches(marker_root, repo_root, run_git):
    if not isinstance(marker_root, str) or not marker_root.strip():
        return False, "repoRoot is missing or empty"
    if not os.path.isabs(marker_root):
        return False, "repoRoot is not absolute"
    toplevel = _worktree_toplevel(repo_root, run_git)
    if toplevel is None:
        return False, "worktree toplevel could not be resolved"
    if os.path.realpath(marker_root) != os.path.realpath(toplevel):
        return False, "repoRoot does not match this worktree"
    return True, None


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        return None, str(exc)
    if not isinstance(data, dict):
        return None, "not a JSON object"
    return data, None


def _validate_build_lane(obj, repo_root, run_git):
    if obj.get("schema") != BUILD_LANE_SCHEMA:
        return False, "schema must be build-lane/1"
    if obj.get("lane") != "full":
        return None, "non-full-lane"
    for key in ("issue", "declaredAt", "repoRoot"):
        if not isinstance(obj.get(key), str) or not obj.get(key):
            return False, "missing or empty field: %s" % key
    ok, why = _marker_repo_matches(obj["repoRoot"], repo_root, run_git)
    if not ok:
        return False, why
    return True, None


def _validate_review_session(obj, repo_root, run_git):
    if obj.get("schema") != REVIEW_SESSION_SCHEMA:
        return False, "schema must be review-session/1"
    for key in ("sessionDir", "startedAt", "repoRoot"):
        if not isinstance(obj.get(key), str) or not obj.get(key):
            return False, "missing or empty field: %s" % key
    ok, why = _marker_repo_matches(obj["repoRoot"], repo_root, run_git)
    if not ok:
        return False, why
    return True, None


def _marker_clearing_hint(path):
    return "remove or repair %s so repoRoot matches this worktree" % path


def marker_state(gitdir, repo_root, *, run_git=None):
    """Return scope markers beside the sidecar under ``gitdir``."""
    run_git = run_git or store_core.run_git
    super_dir = os.path.join(gitdir, _SIDECAR_DIR)
    markers = []
    stale = []
    for name, validator in (
        (BUILD_LANE_FILE, _validate_build_lane),
        (REVIEW_SESSION_FILE, _validate_review_session),
    ):
        path = os.path.join(super_dir, name)
        if not os.path.isfile(path):
            continue
        obj, err = _read_json(path)
        if obj is None:
            stale.append((path, err or "unreadable"))
            continue
        ok, reason = validator(obj, repo_root, run_git)
        if ok is True:
            markers.append(path)
        elif ok is False:
            stale.append((path, reason))
        # ok is None → non-full build lane or other out-of-scope marker; ignore silently
    return {"inScope": bool(markers), "markers": markers, "stale": stale}


def _sidecar_path(gitdir):
    return os.path.join(gitdir, _SIDECAR_DIR, _SIDECAR_FILE)


def _allow(subject=None, detail=""):
    return {
        "schema": SCHEMA,
        "decision": "allow",
        "reason": None,
        "detail": detail,
        "subject": subject or _empty_subject(),
        "sidecarPath": None,
    }


def _empty_subject():
    return {"repo": None, "selector": None, "head": None, "base": None, "repoSource": None}


def _refuse(reason, detail, *, subject=None, sidecar_path=None, head_sha=None):
    if head_sha:
        base = _REFUSAL_DETAIL % head_sha
        detail = (base + (" " + detail if detail else "")).strip()
    return {
        "schema": SCHEMA,
        "decision": "refuse",
        "reason": reason,
        "detail": detail.strip(),
        "subject": subject or _empty_subject(),
        "sidecarPath": sidecar_path,
    }


def _recompute_base_sha(base_ref, repo_root, run_git):
    return run_git(repo_root, "rev-parse", "--verify", "--quiet", "%s^{commit}" % base_ref)


def _recompute_diff_sha256(base_sha, repo_root):
    """Pinned diff recompute — subprocess for git -c flags."""
    try:
        r = subprocess.run(
            ["git", "-C", repo_root, "-c", "core.quotepath=false",
             "diff", "--no-color", "--no-ext-diff", "%s...HEAD" % base_sha],
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return hashlib.sha256(r.stdout).hexdigest()


def _read_receipt(path):
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return None, None
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return raw, None
    return raw, obj


def _verdict_allowlisted(sidecar, receipt):
    verdict = sidecar.get("verdict")
    if verdict not in HANDBACK_VERDICT_ALLOWLIST:
        return False
    if verdict == "converged":
        return isinstance(receipt.get("certification"), dict)
    if verdict == RD.ATTESTED_VERDICT:
        return isinstance(receipt.get("attestation"), dict)
    return False


def _validate_binding(invocation, cwd, environ, run_git, gitdir, scope):
    subject = command_subject(invocation, environ)
    sidecar_path = _sidecar_path(gitdir)
    head_sha = run_git(cwd, "rev-parse", "HEAD")
    if not head_sha:
        return _refuse("handback-inspection-failed",
                        "git could not resolve HEAD",
                        subject=subject, sidecar_path=sidecar_path)

    if invocation.get("parse_error"):
        return _refuse("handback-inspection-failed",
                        "could not parse gh pr flags",
                        subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)

    if not os.path.isfile(sidecar_path):
        return _refuse("handback-no-receipt", "",
                        subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)

    sidecar, err = _read_json(sidecar_path)
    if sidecar is None:
        return _refuse("handback-receipt-unreadable",
                        "sidecar unreadable: %s" % err,
                        subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)

    ok, why = RR.validate_sidecar(sidecar)
    if not ok:
        return _refuse("handback-receipt-unreadable",
                        "sidecar invalid: %s" % why,
                        subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)

    receipt_path = sidecar.get("receiptPath")
    receipt_bytes, receipt = _read_receipt(receipt_path)
    if receipt_bytes is None:
        return _refuse("handback-receipt-unreadable",
                        "receipt at %r is unreadable" % receipt_path,
                        subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)
    if hashlib.sha256(receipt_bytes).hexdigest() != sidecar.get("receiptSha256"):
        return _refuse("handback-receipt-unreadable",
                        "receipt bytes do not match receiptSha256",
                        subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)
    if receipt is None:
        return _refuse("handback-receipt-unreadable",
                        "receipt at %r is not valid JSON" % receipt_path,
                        subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)

    if not _verdict_allowlisted(sidecar, receipt):
        return _refuse("handback-verdict-not-allowlisted", "",
                        subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)

    if head_sha != sidecar.get("headSha"):
        return _refuse("handback-head-mismatch", "",
                        subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)

    origin = store_core.normalize_remote(run_git(cwd, "remote", "get-url", "origin"))
    if origin is None or origin != sidecar.get("repoId"):
        return _refuse("handback-repo-mismatch",
                        "origin %r does not match sidecar repoId %r"
                        % (origin, sidecar.get("repoId")),
                        subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)

    if subject.get("repo") and subject["repo"] != sidecar.get("repoId"):
        return _refuse("handback-repo-mismatch",
                        "command repo %r does not match sidecar repoId %r"
                        % (subject["repo"], sidecar.get("repoId")),
                        subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)

    action = invocation.get("action")
    pr = invocation.get("pr") or {}

    if action == "pr-ready" and pr.get("selector"):
        return _refuse("handback-subject-unresolvable",
                        "explicit PR selector on pr ready cannot be proven locally",
                        subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)

    if pr.get("head"):
        branch = run_git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
        if branch and pr["head"] != branch:
            return _refuse("handback-subject-unresolvable",
                            "--head %r does not match worktree branch %r"
                            % (pr["head"], branch),
                            subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)

    if action == "pr-create":
        if pr.get("base") is None:
            return _refuse("handback-subject-unresolvable",
                            "pr create without --base cannot be bound to sidecar baseRef locally",
                            subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)
        if pr["base"] != sidecar.get("baseRef"):
            return _refuse("handback-base-mismatch",
                            "--base %r does not match sidecar baseRef %r"
                            % (pr["base"], sidecar.get("baseRef")),
                            subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)

    base_ref = sidecar.get("baseRef")
    recomputed_base = _recompute_base_sha(base_ref, cwd, run_git)
    if not recomputed_base:
        return _refuse("handback-inspection-failed",
                        "git rev-parse for baseRef %r failed" % base_ref,
                        subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)

    if recomputed_base != sidecar.get("baseSha"):
        return _refuse("handback-diff-mismatch",
                        "recomputed baseSha %r does not match sidecar" % recomputed_base,
                        subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)

    recomputed_diff = _recompute_diff_sha256(recomputed_base, cwd)
    if recomputed_diff is None:
        return _refuse("handback-inspection-failed",
                        "diff recompute for %s...HEAD failed" % recomputed_base,
                        subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)

    if recomputed_diff != sidecar.get("diffSha256"):
        return _refuse("handback-diff-mismatch",
                        "recomputed diffSha256 does not match sidecar",
                        subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)

    return _allow(subject=subject, detail="valid receipt bound")


def validate_handback(command, cwd, *, environ=None, run_git=None):
    """Decide whether a bash command may hand back (ready/create a non-draft PR)."""
    environ = environ if environ is not None else os.environ
    run_git = run_git or store_core.run_git
    invocations = parse_gh_invocations(command)
    guarded = [inv for inv in invocations
               if inv["action"] in ("pr-ready", "pr-create", "graphql-ready")
               and not (inv["action"] == "pr-ready" and inv.get("undo"))
               and not (inv["action"] == "pr-create" and inv.get("draft"))]

    if not guarded:
        return _allow()

    try:
        gitdir = store_core.get_worktree_gitdir(cwd)
    except store_core.RepoRootUnavailable as exc:
        return _refuse("handback-inspection-failed",
                        "gitdir unresolvable: %s" % exc)

    scope = marker_state(gitdir, cwd, run_git=run_git)
    if not scope["inScope"]:
        if scope["stale"] and not scope["markers"]:
            path, reason = scope["stale"][0]
            detail = ("stale marker at %s (%s) — %s"
                      % (path, reason, _marker_clearing_hint(path)))
            return _refuse("handback-marker-stale", detail,
                            subject=command_subject(guarded[0], environ))
        return _allow()

    for inv in guarded:
        if inv["action"] == "graphql-ready":
            subject = command_subject(inv, environ)
            head_sha = run_git(cwd, "rev-parse", "HEAD")
            return _refuse("handback-inspection-failed",
                            "graphql markPullRequestReadyForReview is refused conservatively",
                            subject=subject, sidecar_path=_sidecar_path(gitdir),
                            head_sha=head_sha)
        result = _validate_binding(inv, cwd, environ, run_git, gitdir, scope)
        if result["decision"] == "refuse":
            return result

    return _allow(subject=command_subject(guarded[-1], environ))
