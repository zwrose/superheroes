#!/usr/bin/env python3
"""Review diff-base guard machinery (#648).

Deterministic, stdlib-only, fail-closed decider for the #637/#641 class: a pinned remote base,
repo binding, fork detection, and round-diff shape. Junk in → conservative out + a named reason;
never certify on silence. The only two git operations used here are read-only (`rev-parse`,
`remote get-url`).

Deliberate non-goal: the head-side fork gap (a PR whose head branch lives in a fork, which
`git fetch origin "$PR_BRANCH"` cannot reach — see review-code SKILL ~line 230) is out of scope
for #648. Fork support on the base side (fetching the base by URL) is deliberately deferred
until a named consumer exists — detect and fail loud only.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import store_core  # noqa: E402

REASON_META_UNREADABLE = "base-meta-unreadable"
REASON_NOT_PINNED = "base-not-pinned"
REASON_UNRESOLVED = "base-unresolved"
REASON_PIN_MOVED = "base-pin-moved"
REASON_REPO_MISMATCH = "base-repo-mismatch"
REASON_PR_REPO_UNRESOLVED = "pr-base-repo-unresolved"
REASON_ORIGIN_UNRESOLVED = "origin-unresolved"
REASON_DIFF_REQUIRED = "round-diff-required"
REASON_DIFF_UNREADABLE = "round-diff-unreadable"
REASON_DIFF_EMPTY = "round-diff-empty"
REASON_DIFF_MALFORMED = "round-diff-malformed"
REASON_REPO_ROOT_MISMATCH = "base-repo-root-mismatch"

_PIN_SHA1 = re.compile(r"^[0-9a-fA-F]{40}$")
_PIN_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")

_PR_URL = re.compile(
    r"^(?P<base>[a-zA-Z][a-zA-Z0-9+.\-]*://[^/]+/[^/]+/[^/]+)/pull/\d+(?:[/?#].*)?$"
)


def read_meta(session_dir):
    """Read session meta.json. Returns (True, dict) or (False, detail). Never raises."""
    path = os.path.join(session_dir, "meta.json")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except OSError as e:
        return False, "meta.json not readable: %s" % e
    except (ValueError, UnicodeDecodeError) as e:
        return False, "meta.json not parseable: %s" % e
    if not isinstance(data, dict):
        return False, "meta.json is not a JSON object"
    return True, data


def _pin_shape_ok(ref):
    if not isinstance(ref, str):
        return False
    # git rev-parse --verify --quiet "main^{commit}" succeeds on a branch name, so rev-parse
    # alone still admits the substitution review-code forbids ("never let a caller 'recover' by
    # substituting a branch name"). Requiring a full object id makes that enforceable.
    return bool(_PIN_SHA1.match(ref) or _PIN_SHA256.match(ref))


def resolve_commit(ref, repo_root, run=None):
    """Verify ref is a pinned commit object id in repo_root. Returns lowercased pin or None."""
    if run is None:
        run = store_core.run_git
    if not _pin_shape_ok(ref):
        return None
    out = run(repo_root, "rev-parse", "--verify", "--quiet", "%s^{commit}" % ref)
    if out is None:
        return None
    # <x>^{commit} peels annotated tags to their target commit; the pin must be the commit
    # itself, not a tag object id that would peel to a different hash.
    if out.strip().lower() != ref.lower():
        return None
    return ref.lower()


def _resolve_commit_reason(ref, repo_root, run):
    """Like resolve_commit but distinguishes shape failure from git disagreement."""
    if not _pin_shape_ok(ref):
        return None, REASON_NOT_PINNED
    pin = resolve_commit(ref, repo_root, run=run)
    if pin is None:
        return None, REASON_UNRESOLVED
    return pin, None


def parse_pr_base_repo(url):
    """Extract normalized base repo from a PR URL.

    gh pr view --json has no baseRepository field (it offers baseRefName, headRepository,
    headRepositoryOwner, isCrossRepository, url), so url is the base-repo source of truth.
    """
    if not isinstance(url, str):
        return None
    m = _PR_URL.match(url)
    if not m:
        return None
    return store_core.normalize_remote(m.group("base"))


def pr_base_repo(session_dir):
    """Normalized base repo from session pr.json, or None. Never raises."""
    path = os.path.join(session_dir, "pr.json")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    url = data.get("url")
    return parse_pr_base_repo(url)


def origin_repo(repo_root, run=None):
    """Normalized origin remote URL, or None. Never raises."""
    if run is None:
        run = store_core.run_git
    try:
        raw = run(repo_root, "remote", "get-url", "origin")
        return store_core.normalize_remote(raw)
    except Exception:
        return None


def check_round_diff(path):
    """Validate a round diff artifact. Fail-closed on missing, empty, or non-diff content."""
    if not path:
        return {
            "ok": False,
            "reason": REASON_DIFF_REQUIRED,
            "detail": "round diff path is required",
        }
    try:
        with open(path, encoding="utf-8") as fh:
            content = fh.read()
    except (OSError, UnicodeDecodeError) as e:
        return {
            "ok": False,
            "reason": REASON_DIFF_UNREADABLE,
            "detail": "round diff not readable: %s" % e,
        }
    # An empty review surface is never certifiable-clean; git diff <empty>...HEAD reads as
    # HEAD...HEAD and exits 0 with zero lines, and git diff null...HEAD exits 128 while still
    # leaving an empty diff.txt.
    if not content or not content.strip():
        return {
            "ok": False,
            "reason": REASON_DIFF_EMPTY,
            "detail": "round diff is empty or whitespace-only",
        }
    # Shell redirection creates the artifact before git diff finishes, so a failed diff can
    # leave non-empty bytes behind. This catches cases where those bytes are not git-diff output
    # at all (a redirected error stream, or a write that never reached the first header). Mid-
    # stream truncation of an otherwise well-formed diff is not detectable from the artifact alone
    # — the primary defence against a failed producer is the SKILL's atomic publish (write to
    # .tmp, mv only on exit 0), so a failed diff leaves no artifact and REASON_DIFF_UNREADABLE
    # fires. Every non-empty git diff output carries at least one `diff --git ` header — including
    # renames, mode-only changes, and binary diffs — so this check has no false positives on real
    # output. Do not use delta_surface.parse_hunks here: it returns None for legitimate rename-
    # only or binary diffs, so None is not a malformed signal.
    has_header = any(line.startswith("diff --git ") for line in content.splitlines())
    if not has_header:
        return {
            "ok": False,
            "reason": REASON_DIFF_MALFORMED,
            "detail": "round diff has no git diff header",
        }
    return {"ok": True, "text": content}


def check_base(session_dir, repo_root, prior_pin=None, run=None):
    """Single entry point: validate session base pin and repo binding. Fail-closed."""
    if run is None:
        run = store_core.run_git

    ok_meta, meta_or_detail = read_meta(session_dir)
    if not ok_meta:
        return {
            "ok": False,
            "reason": REASON_META_UNREADABLE,
            "detail": meta_or_detail,
        }
    meta = meta_or_detail

    # Bind the git checkout to the session record. Git worktrees share one object store, so a
    # pinned base commit resolves perfectly well from the wrong worktree, and origin matches there
    # too. Without this binding the guard would pass while the diff under review came from a
    # different checkout. meta.repo comes from gh repo view's ambiguous resolution; meta.headSha
    # resolves through the same shared object store — neither substitutes for repoRoot binding.
    meta_root = meta.get("repoRoot")
    if not isinstance(meta_root, str):
        return {
            "ok": False,
            "reason": REASON_REPO_ROOT_MISMATCH,
            "detail": "meta.repoRoot is missing or not a string",
        }
    toplevel = run(repo_root, "rev-parse", "--show-toplevel")
    if toplevel is None:
        return {
            "ok": False,
            "reason": REASON_REPO_ROOT_MISMATCH,
            "detail": "repo_root is not a git repository (cannot resolve toplevel)",
        }
    meta_rp = os.path.realpath(meta_root)
    checkout_rp = os.path.realpath(toplevel)
    if meta_rp != checkout_rp:
        return {
            "ok": False,
            "reason": REASON_REPO_ROOT_MISMATCH,
            "detail": "repoRoot %r does not match checkout toplevel %r"
            % (meta_rp, checkout_rp),
        }

    pin, pin_reason = _resolve_commit_reason(meta.get("baseRef"), repo_root, run)
    if pin is None:
        ref_repr = repr(meta.get("baseRef"))
        if pin_reason == REASON_NOT_PINNED:
            detail = "baseRef is not a pinned full object id: %s" % ref_repr
        else:
            detail = "baseRef does not resolve in this repository: %s" % ref_repr
        return {"ok": False, "reason": pin_reason, "detail": detail}

    if prior_pin is not None and pin != prior_pin.lower():
        return {
            "ok": False,
            "reason": REASON_PIN_MOVED,
            "detail": "base pin moved from %s to %s" % (prior_pin, pin),
        }

    mode = meta.get("mode")
    base_repo = origin_repo(repo_root, run=run)
    base_repo_check = "not-applicable-branch-mode"
    # Branch mode's base is origin/HEAD, i.e. origin by construction — nothing to compare.
    if mode == "pr":
        pr_repo = pr_base_repo(session_dir)
        if pr_repo is None:
            return {
                "ok": False,
                "reason": REASON_PR_REPO_UNRESOLVED,
                "detail": "cannot determine PR base repository from pr.json",
            }
        if base_repo is None:
            return {
                "ok": False,
                "reason": REASON_ORIGIN_UNRESOLVED,
                "detail": "origin remote URL could not be resolved",
            }
        if pr_repo != base_repo:
            return {
                "ok": False,
                "reason": REASON_REPO_MISMATCH,
                "detail": "PR base repo %r does not match origin %r" % (pr_repo, base_repo),
            }
        base_repo_check = "matched"

    return {
        "ok": True,
        "baseRef": pin,
        "baseBranch": meta.get("baseBranch"),
        "baseFetch": meta.get("baseFetch"),
        "mode": mode,
        "baseRepo": base_repo,
        "baseRepoCheck": base_repo_check,
        "repoRoot": checkout_rp,
    }
