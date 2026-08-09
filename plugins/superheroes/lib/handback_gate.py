#!/usr/bin/env python3
"""Handback gate — parser, subject resolver, semantic validator, scope markers (#624 §4).

Refuses ``gh pr ready`` / non-draft ``gh pr create`` in a mechanically-marked full-lane worktree
that lacks an allowlisted review receipt. This class is a **Claude-host, Bash-tool, honest-agent
tripwire**. It does not cover aliases, wrapper scripts, non-Bash tools, or other hosts. **It is
not a security boundary and is not claimed as one.**

Parser invariants (re-grounded #624 WO-7):

**(a) An unknown flag must never shift the interpretation of any other token.** Cursor advancement
is decided in exactly one place per token; an unrecognized flag advances by exactly one.

**(b) The gate allows only what §4.3's binding can actually verify against the sidecar, and refuses
nothing a genuinely-valid production case produces.** Where the honest resolution is *cannot verify
deterministically*, that is a stated residual covered by the advisor vet — exactly as ratified §4.3
already does for ``gh pr ready``'s remote base. State the residual; never invent verification.

**``gh pr ready`` residual:** for a bare ``gh pr ready`` with no selector, binding is branch +
HEAD — the PR's remote base cannot be resolved without a network call inside a deterministic hook.
That residual is covered by the advisor vet's existing remote-head duty. An explicit selector is a
different case and refuses ``handback-subject-unresolvable``.

**``gh pr create`` without ``--base`` residual:** when neither ``branch.<current>.gh-merge-base``
nor ``refs/remotes/origin/HEAD`` resolves locally, implicit base cannot be bound and the command
refuses ``handback-subject-unresolvable`` — the same class as an explicit selector on ``pr ready``.

**Segment cwd residual:** guarded ``gh`` in a segment whose working directory cannot be established
(any preceding ``cd``/``pushd``, or a subshell wrapper) refuses ``handback-inspection-failed``.
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
HANDBACK_VERDICT_ALLOWLIST = ("converged", RD.ATTESTED_VERDICT)

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
_GH_HOST_REPO_SLUG = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_LEGACY_BASE_SHA = re.compile(r"^[0-9a-f]{40}$")
_HEREDOC_OPENER = re.compile(r"<<-?\s*(['\"]?)(\w+)\1\s*$")

_ENV_ASSIGN_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# gh pr subcommand flags — invariant (a): width is decided once per original argv token.
_GH_PR_VALUE_OPTS = frozenset({"-R", "--repo", "-H", "--head", "-B", "--base"})
_GH_PR_BOOL_OPTS = frozenset({"-d", "--draft", "--undo"})

# gh global flags before the subcommand (``gh -R org/repo pr …``).
_GH_GLOBAL_VALUE_OPTS = frozenset({"-R", "--repo", "--hostname"})

_HAND_BACK_SHELL_PREFIXES = frozenset({
    "!", "then", "do", "else", "elif", "(", ";;", "if",
})

_CWD_CHANGERS = frozenset({"cd", "pushd"})


def _strip_handback_shell_prefixes(tokens):
    """Strip leading shell reserved words so ``if gh pr ready`` is visible."""
    while tokens:
        tok = tokens[0]
        if tok in _HAND_BACK_SHELL_PREFIXES or tok.startswith(";;"):
            tokens = tokens[1:]
            continue
        if tok == "{":
            tokens = tokens[1:]
            continue
        if tok.startswith("{") and len(tok) > 1:
            tokens = [tok[1:]] + tokens[1:]
            continue
        if tok.startswith("(") and len(tok) > 1:
            tokens = [tok[1:]] + tokens[1:]
            continue
        break
    return tokens


def _is_gh_token(token):
    base = os.path.basename(token)
    return base == "gh" or base == "gh.exe"


def _parse_bool_value(raw):
    """Parse an explicit boolean flag value. None means unparseable."""
    if raw is None:
        return True
    low = str(raw).lower()
    if low in ("false", "0", "no"):
        return False
    if low in ("true", "1", "yes", ""):
        return True
    return None


def _option_token_width(tokens, idx, value_taking):
    """How many argv slots one option token consumes — invariant (a)."""
    tok = tokens[idx]
    if "=" in tok:
        return 1
    if value_taking:
        return 2 if idx + 1 < len(tokens) else 1
    return 1


def _inline_option_value(tok):
    if "=" in tok:
        return tok.split("=", 1)[1]
    return None


def _expand_clustered_flags(token, value_opts):
    """Minimal clustered-short-flag expander for gh pr flags."""
    if not token.startswith("-") or token.startswith("--"):
        if token.startswith("--"):
            base = token.split("=", 1)[0]
            expects = base in value_opts and "=" not in token
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
        if opt in value_opts:
            rest = letters[i + 1:]
            if rest:
                return (flags, rest, False)
            return (flags, None, True)
        i += 1
    return (flags, None, False)


def _parse_pr_args(args):
    """Parse flags and operands for ``gh pr ready`` / ``gh pr create``.

    Invariant (a): each original argv token advances the cursor exactly once via
    ``_option_token_width``; unknown flags touch no state."""
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

        flags, inline, expects_value = _expand_clustered_flags(tok, _GH_PR_VALUE_OPTS)
        width = _option_token_width(args, i, expects_value)
        if expects_value and width == 1 and "=" not in tok:
            parse_error = True

        for part in flags:
            base_flag = part.split("=", 1)[0]
            inline_val = _inline_option_value(part)
            if inline_val is None:
                inline_val = inline

            if base_flag in _GH_PR_BOOL_OPTS:
                parsed = _parse_bool_value(inline_val)
                if parsed is None:
                    parse_error = True
                elif base_flag in ("-d", "--draft"):
                    draft = parsed
                elif base_flag == "--undo":
                    undo = parsed
            elif base_flag in _GH_PR_VALUE_OPTS:
                val = inline_val
                if val is None and width > 1:
                    val = args[i + 1]
                if val is None:
                    parse_error = True
                elif base_flag in ("-R", "--repo"):
                    repo = val
                elif base_flag in ("-H", "--head"):
                    head = val
                elif base_flag in ("-B", "--base"):
                    base = val
            # unknown flag: invariant (a) — no state change, width already set

        i += width

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


def _parse_gh_globals(tokens):
    """Parse inherited ``-R``/``--repo``/``--hostname`` before the ``pr`` subcommand."""
    repo = host = None
    parse_error = False
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok in ("pr", "api"):
            break
        if not tok.startswith("-"):
            i += 1
            continue
        base = tok.split("=", 1)[0]
        if base in _GH_GLOBAL_VALUE_OPTS:
            val = _inline_option_value(tok)
            width = _option_token_width(tokens, i, val is None)
            if val is None and width > 1:
                val = tokens[i + 1]
            if val is None:
                parse_error = True
            elif base in ("-R", "--repo"):
                repo = val
            elif base == "--hostname":
                host = val
            i += width
        else:
            i += 1  # invariant (a): unknown global flag, advance one
    return repo, host, tokens[i:], parse_error


def _classify_gh(tokens, segment_text):
    """Classify one tokenized gh invocation."""
    if not tokens or not _is_gh_token(tokens[0]):
        return None
    global_repo, global_host, rest, global_parse_error = _parse_gh_globals(tokens[1:])
    if len(rest) >= 2 and rest[0] == "api" and rest[1] == "graphql":
        if "markPullRequestReadyForReview" in segment_text:
            return {"action": "graphql-ready", "argv": tokens, "draft": False, "undo": False,
                    "parse_error": global_parse_error, "pr": {},
                    "global_repo": global_repo, "global_host": global_host}
        return None
    if len(rest) >= 2 and rest[0] == "pr":
        sub = rest[1]
        pr_args = rest[2:]
        parsed = _parse_pr_args(pr_args)
        parsed["parse_error"] = parsed["parse_error"] or global_parse_error
        if global_repo and parsed.get("repo") is None:
            parsed["repo"] = global_repo
        if sub == "ready":
            if parsed["undo"]:
                return {"action": "pr-ready", "argv": tokens, "draft": False, "undo": True,
                        "parse_error": parsed["parse_error"], "pr": parsed,
                        "global_repo": global_repo, "global_host": global_host}
            return {"action": "pr-ready", "argv": tokens, "draft": False, "undo": False,
                    "parse_error": parsed["parse_error"], "pr": parsed,
                    "global_repo": global_repo, "global_host": global_host}
        if sub == "create":
            if parsed["draft"]:
                return {"action": "pr-create", "argv": tokens, "draft": True, "undo": False,
                        "parse_error": parsed["parse_error"], "pr": parsed,
                        "global_repo": global_repo, "global_host": global_host}
            return {"action": "pr-create", "argv": tokens, "draft": False, "undo": False,
                    "parse_error": parsed["parse_error"], "pr": parsed,
                    "global_repo": global_repo, "global_host": global_host}
    return None


def _strip_heredoc_bodies(command):
    """Exclude heredoc body lines from command-position scanning — invariant (b)."""
    if not isinstance(command, str) or "\n" not in command:
        return command
    lines = command.split("\n")
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _HEREDOC_OPENER.search(line)
        if m is None:
            out.append(line)
            i += 1
            continue
        delim = m.group(2)
        out.append(line[:m.start()] + m.group(0).rstrip())
        i += 1
        while i < len(lines) and lines[i].strip() != delim:
            i += 1
        if i < len(lines):
            i += 1
    return "\n".join(out)


def _segment_marks_cwd_unestablishable(segment):
    """True when this segment changes cwd or wraps a subshell — invariant (b)."""
    if "(" in segment and segment.lstrip().startswith("("):
        return True
    tokens = _tokenize_segment(segment)
    _, tokens = _capture_env_prefix(tokens)
    tokens = _strip_handback_shell_prefixes(tokens)
    if tokens and tokens[0] in _CWD_CHANGERS:
        return True
    return False


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


def _command_segments(command):
    """Segments at shell boundaries plus substitution inners — invariant (b)."""
    segments = list(_split_segments(command))
    extras = []
    for seg in segments:
        for inner in re.findall(r"\$\(([^)]*)\)", seg):
            if inner.strip():
                extras.append(inner.strip())
        for inner in re.findall(r"`([^`]*)`", seg):
            if inner.strip():
                extras.append(inner.strip())
    return segments + extras


def parse_gh_invocations(command):
    """Parse bash command text for guarded ``gh`` invocations."""
    if not isinstance(command, str):
        return []
    command = _strip_heredoc_bodies(command)
    invocations = []
    cwd_establishable = True
    for segment in _command_segments(command):
        if _segment_marks_cwd_unestablishable(segment):
            cwd_establishable = False
        tokens = _tokenize_segment(segment)
        if not tokens:
            continue
        inline_env, tokens = _capture_env_prefix(tokens)
        tokens = _strip_handback_shell_prefixes(tokens)
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
            "cwd_establishable": cwd_establishable,
        }
        if classified.get("global_host"):
            inv["env"]["GH_HOST"] = classified["global_host"]
        for key in ("GH_REPO", "GH_HOST"):
            if key in inline_env:
                inv["env"][key] = inline_env[key]
        invocations.append(inv)
    return invocations


def _normalize_repo_arg(value, host=None):
    if not value:
        return None
    m = _PR_URL.match(value)
    if m:
        return store_core.normalize_remote(m.group("base"))
    if _GH_HOST_REPO_SLUG.match(value):
        parts = value.split("/", 2)
        return "%s/%s/%s" % (parts[0].lower(), parts[1], parts[2])
    if _GH_REPO_SLUG.match(value):
        use_host = (host or "github.com").lower()
        return "%s/%s" % (use_host, value)
    return store_core.normalize_remote(value)


def command_subject(invocation, environ=None):
    """Resolve repo/selector/head/base from one parsed gh invocation."""
    environ = environ if environ is not None else os.environ
    pr = invocation.get("pr") or {}
    inline = invocation.get("env") or {}
    host = inline.get("GH_HOST") or environ.get("GH_HOST")
    repo = pr.get("repo")
    repo_source = None
    if repo:
        repo_source = "flag"
        repo = _normalize_repo_arg(repo, host=host)
    selector = pr.get("selector")
    head = pr.get("head")
    base = pr.get("base")
    for operand in _pr_url_operands(invocation):
        if selector is None:
            selector = operand
        parsed = _normalize_repo_arg(operand, host=host)
        if parsed and repo is None:
            repo = parsed
            repo_source = "url"
    if repo is None and inline.get("GH_REPO"):
        repo = _normalize_repo_arg(inline["GH_REPO"], host=host)
        repo_source = "env-inline"
    if repo is None and environ.get("GH_REPO"):
        repo = _normalize_repo_arg(environ["GH_REPO"], host=host)
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


def _worktree_toplevel(repo_root):
    """Repo root via store_core, the one sanctioned resolver (`test_repo_root_census`)."""
    try:
        return store_core.repo_root(repo_root)
    except store_core.RepoRootUnavailable:
        return None


def _marker_repo_matches(marker_root, repo_root):
    if not isinstance(marker_root, str) or not marker_root.strip():
        return False, "repoRoot is missing or empty"
    if not os.path.isabs(marker_root):
        return False, "repoRoot is not absolute"
    toplevel = _worktree_toplevel(repo_root)
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


def _validate_build_lane(obj, repo_root):
    if obj.get("schema") != BUILD_LANE_SCHEMA:
        return False, "schema must be build-lane/1"
    if obj.get("lane") != "full":
        return None, "non-full-lane"
    for key in ("issue", "declaredAt", "repoRoot"):
        if not isinstance(obj.get(key), str) or not obj.get(key):
            return False, "missing or empty field: %s" % key
    ok, why = _marker_repo_matches(obj["repoRoot"], repo_root)
    if not ok:
        return False, why
    return True, None


def _validate_review_session(obj, repo_root):
    if obj.get("schema") != REVIEW_SESSION_SCHEMA:
        return False, "schema must be review-session/1"
    for key in ("sessionDir", "startedAt", "repoRoot"):
        if not isinstance(obj.get(key), str) or not obj.get(key):
            return False, "missing or empty field: %s" % key
    ok, why = _marker_repo_matches(obj["repoRoot"], repo_root)
    if not ok:
        return False, why
    return True, None


def marker_state(gitdir, repo_root):
    """Return scope markers beside the sidecar under ``gitdir``."""
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
        ok, reason = validator(obj, repo_root)
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


def _resolve_implicit_pr_base(cwd, run_git):
    """Resolve ``gh pr create`` implicit ``--base`` from local git config — invariant (b)."""
    branch = run_git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    if branch and branch != "HEAD":
        merge_base = run_git(cwd, "config", "--get", "branch.%s.gh-merge-base" % branch)
        if merge_base:
            return merge_base
    sym = run_git(cwd, "symbolic-ref", "refs/remotes/origin/HEAD")
    if sym:
        ref = sym.strip()
        prefix = "refs/remotes/origin/"
        if ref.startswith(prefix):
            return ref[len(prefix):]
    return None


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


def _receipt_bindings_ok(sidecar, receipt):
    """Delegate receipt shape to ``round_driver.validate_receipt``; layer verdict allowlist on top."""
    ok, why = RD.validate_receipt(receipt)
    if not ok:
        return False, "receipt-invalid:%s" % why
    if receipt.get("verdict") != sidecar.get("verdict"):
        return False, "verdict-mismatch"
    verdict = sidecar.get("verdict")
    if verdict not in HANDBACK_VERDICT_ALLOWLIST:
        return False, "verdict-not-allowlisted"
    if verdict == "converged":
        if not isinstance(receipt.get("certification"), dict):
            return False, "no-certification"
    elif verdict == RD.ATTESTED_VERDICT:
        if not isinstance(receipt.get("attestation"), dict):
            return False, "no-attestation"
    return True, None


def _validate_binding(invocation, cwd, environ, run_git, gitdir):
    subject = command_subject(invocation, environ)
    sidecar_path = _sidecar_path(gitdir)
    head_sha = run_git(cwd, "rev-parse", "HEAD")
    if not head_sha:
        return _refuse("handback-inspection-failed",
                        "git could not resolve HEAD",
                        subject=subject, sidecar_path=sidecar_path)

    if not invocation.get("cwd_establishable", True):
        return _refuse("handback-inspection-failed",
                        "working directory for this gh invocation cannot be established "
                        "(preceding cd/pushd or subshell)",
                        subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)

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

    if _LEGACY_BASE_SHA.match(sidecar.get("baseRef") or ""):
        return _refuse("handback-receipt-unreadable",
                        "sidecar baseRef carries a commit id (legacy writer); "
                        "republish sidecar with base branch name",
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

    bindings_ok, bind_why = _receipt_bindings_ok(sidecar, receipt)
    if not bindings_ok:
        if bind_why and bind_why.startswith("receipt-invalid:"):
            return _refuse("handback-receipt-unreadable",
                            "receipt invalid: %s" % bind_why[len("receipt-invalid:"):],
                            subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)
        return _refuse("handback-verdict-not-allowlisted", "",
                        subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)

    if head_sha != sidecar.get("headSha"):
        return _refuse("handback-head-mismatch", "",
                        subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)

    branch = run_git(cwd, "rev-parse", "--abbrev-ref", "HEAD")
    if branch and branch != sidecar.get("branch"):
        return _refuse("handback-branch-mismatch",
                        "worktree branch %r does not match sidecar branch %r"
                        % (branch, sidecar.get("branch")),
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
        if branch and pr["head"] != branch:
            return _refuse("handback-subject-unresolvable",
                            "--head %r does not match worktree branch %r"
                            % (pr["head"], branch),
                            subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)

    if action == "pr-create":
        cmd_base = pr.get("base")
        if cmd_base is None:
            cmd_base = _resolve_implicit_pr_base(cwd, run_git)
            if cmd_base is None:
                return _refuse("handback-subject-unresolvable",
                                "pr create without --base cannot be bound to sidecar "
                                "baseRef locally",
                                subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)
        sidecar_base = sidecar.get("baseRef")
        if sidecar_base == "unpinned":
            return _refuse("handback-base-mismatch",
                            "sidecar baseRef is unpinned",
                            subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)
        if cmd_base != sidecar_base:
            return _refuse("handback-base-mismatch",
                            "--base %r does not match sidecar baseRef %r"
                            % (cmd_base, sidecar_base),
                            subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)

    pinned_base = sidecar.get("baseSha")
    if not pinned_base or pinned_base == "unresolved":
        return _refuse("handback-inspection-failed",
                        "sidecar baseSha is not pinned",
                        subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)

    verified_base = run_git(cwd, "rev-parse", "--verify", "--quiet",
                            "%s^{commit}" % pinned_base)
    if not verified_base:
        return _refuse("handback-inspection-failed",
                        "git rev-parse for sidecar baseSha %r failed" % pinned_base,
                        subject=subject, sidecar_path=sidecar_path, head_sha=head_sha)

    recomputed_diff = _recompute_diff_sha256(verified_base, cwd)
    if recomputed_diff is None:
        return _refuse("handback-inspection-failed",
                        "diff recompute for %s...HEAD failed" % verified_base,
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

    scope = marker_state(gitdir, cwd)
    if not scope["inScope"]:
        # §4.2: neither valid marker → silent allow; stale alone is out of scope too.
        return _allow()

    for inv in guarded:
        if inv["action"] == "graphql-ready":
            subject = command_subject(inv, environ)
            head_sha = run_git(cwd, "rev-parse", "HEAD")
            return _refuse("handback-inspection-failed",
                            "graphql markPullRequestReadyForReview is refused conservatively",
                            subject=subject, sidecar_path=_sidecar_path(gitdir),
                            head_sha=head_sha)
        result = _validate_binding(inv, cwd, environ, run_git, gitdir)
        if result["decision"] == "refuse":
            return result

    return _allow(subject=command_subject(guarded[-1], environ))
