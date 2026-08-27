#!/usr/bin/env python3
"""Review diff-base guard machinery (#648).

Deterministic, stdlib-only, fail-closed decider for the #637/#641 class: a pinned remote base,
repo binding, fork detection, and round-diff shape. Junk in → conservative out + a named reason;
never certify on silence. The only two git operations used here are read-only (`rev-parse`,
`remote get-url`).

Deliberate non-goal: the head-side fork gap (a PR whose head branch lives in a fork, which
`git fetch origin "$PR_BRANCH"` cannot reach — see review-code SKILL.md §1 Setup, the "PR mode" block) is out of scope
for #648. Fork support on the base side (fetching the base by URL) is deliberately deferred
until a named consumer exists — detect and fail loud only.
"""
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import session_mode  # noqa: E402
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
REASON_DIFF_BASE_MISMATCH = "round-diff-base-mismatch"
REASON_DIFF_BASE_UNVERIFIABLE = "round-diff-base-unverifiable"
REASON_REPO_ROOT_MISMATCH = "base-repo-root-mismatch"
REASON_MODE_UNRECOGNIZED = "base-mode-unrecognized"

# Closed session modes — authoritative set for check_base and grounding_stage.
SESSION_MODES = session_mode.MODES

META_REASONS = frozenset({"unreadable", "undecodable", "unparseable", "not-an-object"})

_PIN_SHA1 = re.compile(r"^[0-9a-fA-F]{40}$")
_PIN_SHA256 = re.compile(r"^[0-9a-fA-F]{64}$")

_PR_URL = re.compile(
    r"^(?P<base>[a-zA-Z][a-zA-Z0-9+.\-]*://[^/]+/[^/]+/[^/]+)/pull/\d+(?:[/?#].*)?$"
)


def classify_meta(session_dir):
    """Classify meta.json read outcome. Returns (ok, data_or_detail, reason)."""
    path = os.path.join(session_dir, "meta.json")
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as e:
        return False, "meta.json not readable: %s" % e, "unreadable"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        return False, "meta.json not parseable: %s" % e, "undecodable"
    try:
        data = json.loads(text)
    except (ValueError, json.JSONDecodeError) as e:
        return False, "meta.json not parseable: %s" % e, "unparseable"
    if not isinstance(data, dict):
        return False, "meta.json is not a JSON object", "not-an-object"
    return True, data, None


def read_meta(session_dir):
    """Read session meta.json. Returns (True, dict) or (False, detail). Never raises."""
    ok, data_or_detail, _reason = classify_meta(session_dir)
    if ok:
        return True, data_or_detail
    return False, data_or_detail


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


_DIFF_GIT_HEADER = re.compile(r"^diff --git a/(?P<a>.*) b/(?P<b>.*)$")
_PATH_SAMPLE_CAP = 8


def _global_line_counts(file_stats):
    added = deleted = 0
    for val in file_stats.values():
        if val is None:
            continue
        a, d = val
        added += a
        deleted += d
    return added, deleted


def _artifact_diff_stats(diff_text):
    """Per-file line counts from a unified diff artifact (b-side paths).

    Counts only inside hunk bodies (after ``@@``), classifying by the first character — the same
    shape as ``delta_surface.parse_hunks``. File headers ``--- a/x`` / ``+++ b/x`` sit outside
    hunks and are excluded structurally, not by ``+++``/``---`` prefix guessing on every line.

    Split on ``\\n`` rather than ``splitlines()``: splitlines() also breaks on ``\\f``, ``\\x0b``,
    ``\\x85``, and U+2028, which git treats as ordinary in-line bytes; a fragment beginning with
    ``+``/``-`` would then double-count.

    Returns ``(file_stats, headers_parsed, global_added, global_deleted)``. Global totals count
    every in-hunk ``+``/``-`` even when a ``diff --git`` header could not be parsed (quoted paths),
    so ``line-counts-only`` fallback still compares totals.
    """
    file_stats = {}
    headers_parsed = True
    current_b = None
    cur_added = 0
    cur_deleted = 0
    global_added = 0
    global_deleted = 0
    in_hunk = False

    def _flush_file():
        nonlocal cur_added, cur_deleted
        if current_b is None:
            cur_added = cur_deleted = 0
            return
        if current_b in file_stats and file_stats[current_b] is None:
            cur_added = cur_deleted = 0
            return
        prev = file_stats.get(current_b, (0, 0))
        file_stats[current_b] = (prev[0] + cur_added, prev[1] + cur_deleted)
        cur_added = cur_deleted = 0

    for line in (diff_text or "").split("\n"):
        if line.startswith("diff --git "):
            _flush_file()
            in_hunk = False
            m = _DIFF_GIT_HEADER.match(line)
            if m:
                current_b = m.group("b")
            else:
                headers_parsed = False
                current_b = None
            continue
        if line.startswith("@@"):
            in_hunk = True
            continue
        if line.startswith("Binary files ") or line.startswith("GIT binary patch"):
            _flush_file()
            if current_b is not None:
                file_stats[current_b] = None
            in_hunk = False
            continue
        if in_hunk and line:
            kind = line[0]
            if kind == "+":
                global_added += 1
                if current_b is not None:
                    cur_added += 1
            elif kind == "-":
                global_deleted += 1
                if current_b is not None:
                    cur_deleted += 1
            elif kind == "\\":
                pass
    _flush_file()
    return file_stats, headers_parsed, global_added, global_deleted


def _parse_numstat(numstat_out):
    """Build per-file stats from ``git diff --numstat -z`` output.

    NUL-delimited fields: a normal row is ``added\\tdeleted\\tpath``; a rename/copy row is
    ``added\\tdeleted\\t`` followed by old path and new path (new path is used). Values are
    ``(added, deleted)`` tuples or ``None`` for binary rows (``-\\t-\\tpath``).

    Returns ``(file_stats, per_file_ok, global_added, global_deleted)``. ``per_file_ok`` is False
    when any path could not be mapped (caller falls back to global totals only). Global totals
    include every row's counts even when per-file mapping failed. The numstat stream is captured
    as bytes and decoded with ``surrogateescape``, so arbitrary path bytes cannot raise or be
    stripped away during capture.
    """
    file_stats = {}
    per_file_ok = True
    global_added = 0
    global_deleted = 0
    if not numstat_out:
        return file_stats, per_file_ok, global_added, global_deleted

    fields = numstat_out.split("\0")
    while fields and fields[-1] == "":
        fields.pop()

    i = 0
    n = len(fields)
    while i < n:
        row = fields[i]
        parts = row.split("\t")
        if len(parts) < 2:
            per_file_ok = False
            i += 1
            continue
        a, d = parts[0], parts[1]
        if a == "-" or d == "-":
            row_added = row_deleted = 0
        else:
            try:
                row_added, row_deleted = int(a), int(d)
            except ValueError:
                per_file_ok = False
                i += 1
                continue
        global_added += row_added
        global_deleted += row_deleted

        if len(parts) >= 3 and parts[2] != "":
            resolved = parts[2]
            i += 1
        elif len(parts) >= 3 and parts[2] == "":
            if i + 2 < n:
                resolved = fields[i + 2]
                i += 3
            else:
                per_file_ok = False
                i += 1
                continue
        else:
            per_file_ok = False
            i += 1
            continue

        if not resolved:
            per_file_ok = False
            continue

        if a == "-" or d == "-":
            file_stats[resolved] = None
        else:
            file_stats[resolved] = (row_added, row_deleted)

    return file_stats, per_file_ok, global_added, global_deleted


def _run_git_bytes(cwd, *args):
    """Run git with binary stdout (no text decode). Return stdout bytes or None."""
    try:
        r = subprocess.run(
            ["git", "-C", cwd, *args],
            capture_output=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError, ValueError):
        return None
    return r.stdout if r.returncode == 0 else None


def _numstat_z_output(pin, repo_root, run):
    """``git diff --numstat -z`` as a string safe for ``_parse_numstat``.

    ``run`` is a test seam: when supplied, it should return text-mode stdout or ``None``.
    Production must leave ``run`` as ``None`` so stdout is captured as bytes and decoded with
    ``surrogateescape``. Passing ``store_core.run_git`` here reintroduces a ``UnicodeDecodeError``
    on non-UTF-8 paths. If an explicit ``run`` returns ``bytes``, they are decoded the same way.
    """
    if run is None:
        raw = _run_git_bytes(repo_root, "diff", "--numstat", "-z", "%s...HEAD" % pin)
        if raw is None:
            return None
        return raw.decode("utf-8", errors="surrogateescape")
    out = run(repo_root, "diff", "--numstat", "-z", "%s...HEAD" % pin)
    if isinstance(out, bytes):
        return out.decode("utf-8", errors="surrogateescape")
    return out


def _expected_diff_stats(pin, repo_root, run):
    """Per-file stats git would emit for pin...HEAD (one ``--numstat -z`` subprocess)."""
    numstat_out = _numstat_z_output(pin, repo_root, run)
    if numstat_out is None:
        return None
    return _parse_numstat(numstat_out)


def _per_file_mismatch_detail(expected, actual):
    sym = sorted(set(expected) ^ set(actual))
    mismatched = []
    for path in sorted(set(expected) | set(actual)):
        if expected.get(path) != actual.get(path):
            mismatched.append(path)
    sample_paths = mismatched[:_PATH_SAMPLE_CAP]
    bits = []
    for path in sample_paths:
        bits.append("%s exp=%r act=%r" % (path, expected.get(path), actual.get(path)))
    extra = len(mismatched) - len(sample_paths)
    tail = (" (+%d more)" % extra) if extra > 0 else ""
    if sym and not bits:
        bits = ["path set mismatch (sample): %s" % ", ".join(sym[:_PATH_SAMPLE_CAP])]
    return "; ".join(bits) + tail


def check_diff_binding(diff_text, pin, repo_root, run=None):
    """Bind a round diff artifact to the pinned base at file-set + line-count granularity.

    Proves the artifact's shape (paths touched, +/- totals) came from ``git diff <pin>...HEAD``,
    not merely that it looks like a diff. A content-identical substitution that preserves stats is
    deliberately out of scope — full recompute was declined by advisor ruling; a real specimen is the
    upgrade trigger.

    ``run`` is a test seam for git subprocess output. Leave it ``None`` in production so
    ``_numstat_z_output`` captures numstat stdout as bytes with ``surrogateescape``. An explicit
    ``run`` must return text-mode stdout or ``None`` (``bytes`` are coerced); passing
    ``store_core.run_git`` here reintroduces the decode crash on non-UTF-8 paths because that
    helper decodes stdout as UTF-8 text.
    """
    parsed = _expected_diff_stats(pin, repo_root, run)
    if parsed is None:
        return {
            "ok": False,
            "reason": REASON_DIFF_BASE_UNVERIFIABLE,
            "detail": "expected diff could not be recomputed from pin",
        }
    exp_stats, exp_per_file_ok, exp_added, exp_deleted = parsed
    act_stats, headers_ok, act_added, act_deleted = _artifact_diff_stats(diff_text)
    if act_added != exp_added or act_deleted != exp_deleted:
        return {
            "ok": False,
            "reason": REASON_DIFF_BASE_MISMATCH,
            "detail": "artifact +%d/-%d vs pin +%d/-%d"
            % (act_added, act_deleted, exp_added, exp_deleted),
        }
    per_file = headers_ok and exp_per_file_ok
    binding = "line-counts-only"
    if per_file:
        binding = "file-set+line-counts"
        if act_stats != exp_stats:
            return {
                "ok": False,
                "reason": REASON_DIFF_BASE_MISMATCH,
                "detail": _per_file_mismatch_detail(exp_stats, act_stats),
            }
    return {"ok": True, "binding": binding}


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
    # Empty string is not a path: realpath("") silently resolves to cwd, so binding would
    # always pass when meta.repoRoot is blank — the same failure mode as an unset $REPO_ROOT.
    if not meta_root.strip() or not os.path.isabs(meta_root):
        return {
            "ok": False,
            "reason": REASON_REPO_ROOT_MISMATCH,
            "detail": "meta.repoRoot must be a non-empty absolute path, got %r" % meta_root,
        }
    toplevel = run(repo_root, "rev-parse", "--show-toplevel")
    if toplevel is None:
        return {
            "ok": False,
            "reason": REASON_REPO_ROOT_MISMATCH,
            "detail": "repo_root is not a git repository (cannot resolve toplevel)",
        }
    if not toplevel:
        return {
            "ok": False,
            "reason": REASON_REPO_ROOT_MISMATCH,
            "detail": "git rev-parse --show-toplevel returned empty output",
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

    if prior_pin is not None:
        if not isinstance(prior_pin, str):
            return {
                "ok": False,
                "reason": REASON_PIN_MOVED,
                "detail": "stored base pin is not a string: %r" % prior_pin,
            }
        if pin != prior_pin.lower():
            return {
                "ok": False,
                "reason": REASON_PIN_MOVED,
                "detail": "base pin moved from %s to %s" % (prior_pin, pin),
            }

    mode = meta.get("mode")
    # Fail closed: defaulting unrecognized mode to branch mode made the fork check inert when
    # mode was unset; the guard cannot know whether fork comparison applies without a known mode.
    mode_resolved = session_mode.resolve(meta, None)
    if not mode_resolved["resolved"]:
        return {
            "ok": False,
            "reason": REASON_MODE_UNRECOGNIZED,
            "detail": "meta.mode must be 'pr' or 'branch', got %s" % repr(mode),
        }
    base_repo = origin_repo(repo_root, run=run)
    base_repo_check = "not-applicable-branch-mode"
    # Branch mode's base is origin/HEAD, i.e. origin by construction — nothing to compare.
    if mode_resolved["mode"] == session_mode.MODE_PR:
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
        if pr_repo.casefold() != base_repo.casefold():
            return {
                "ok": False,
                "reason": REASON_REPO_MISMATCH,
                "detail": "PR base repo %r does not match origin %r" % (pr_repo, base_repo),
            }
        base_repo_check = "matched"

    # Absent or non-"fetched" baseFetch means unknown provenance — not proof the pin is fresh.
    base_fetch = meta.get("baseFetch")
    base_degraded = base_fetch != "fetched"

    return {
        "ok": True,
        "baseRef": pin,
        "baseBranch": meta.get("baseBranch"),
        "baseFetch": base_fetch,
        "baseDegraded": base_degraded,
        # Single-source (#1107 WO-rc1 I3): `mode_resolved` above is the ONE resolution of this
        # value — the raw `mode` local (read a few lines up) stays only for the refusal `detail`
        # message above, never as a second owner of the returned value.
        "mode": mode_resolved["mode"],
        "baseRepo": base_repo,
        "baseRepoCheck": base_repo_check,
        "repoRoot": checkout_rp,
    }
