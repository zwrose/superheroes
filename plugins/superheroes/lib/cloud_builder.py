"""The cloud builder's machine-side steps: compose and check, never decide the build.

A builder running in a cloud session calls these, through this CLI, at intake, workspace setup,
preflight, review and park.

  cloud_builder.py intake --repo-root D --launch-file F
                          check the launch against this session, then start from its base commit
                          (or, when the launch names a branch to adopt, on that branch at that head);
                          the intake note follows the launch's charter (builder or detective)
  cloud_builder.py ensure-history --repo-root D [--main-branch B]
                          make the clone's history complete and fetch origin/<B>
  cloud_builder.py github-channel --gh-probe-file F --tools-write {ok,failed,not-tried}
                          which channel (gh or the session's GitHub tools) can write
  cloud_builder.py pr-json --repo O/R --branch B --out F
                          the open pull request for a branch, in `gh pr view --json` field names
  cloud_builder.py repo-json --repo O/R
                          the repository's name with owner
  cloud_builder.py post --repo O/R --number N --body-file F
                          one comment on an issue or pull request
  cloud_builder.py note --question-file F
                          the builder note for the advisor, as comment text
  cloud_builder.py edit --repo O/R --comment-id N --body-file F
                          one existing comment rewritten in place
  cloud_builder.py progress --phase P --running R --started T --expected-minutes N [--lost L]
                          the progress comment the builder keeps on its issue, as comment text
  cloud_builder.py review-lapsed
                          the park comment for a lapsed reviewer pass
  cloud_builder.py handover --head SHA
                          the handover comment for work pushed and handed on, naming the head
  cloud_builder.py terminal --kind {handback,stop,park} --text-file F
                          the handback, stop or park comment, headed with its fixed first line
  cloud_builder.py pass-state
                          the placed reviewer sign-in's state, and whether this is a cloud session
  cloud_builder.py superseded --repo O/N --issue N --started T
                          whether a newer launch took the issue over since this builder started (T, UTC
                          ISO); on `superseded: true` the result's `comment` is the stand-down to post
  cloud_builder.py superseded-notice --launch-id L
                          the notice the advisor posts on the issue before it launches a successor

Stdlib only. A function that runs a command or reads the environment takes `env=None` (a mapping;
default the process environment), and one that runs a command also takes `run=None` (default
`subprocess.run`). Every function returns a plain dict; an expected failure is a result with a
`reason` token, never a raise. The CLI prints one JSON object and exits 1 on a refusal.
"""
import argparse
import datetime
import importlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
_GIT_TIMEOUT = 900
_GH_TIMEOUT = 120

_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REPO_RE = re.compile(r"^(?!\.{1,2}/)[A-Za-z0-9_.-]+/(?!\.{1,2}\Z)[A-Za-z0-9_.-]+\Z")
_STARTED_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_EXPECTED_RE = re.compile(r"^Expected:\s*(\d+)\s*minutes?\s*$", re.ASCII)

INTAKE_HEADER = "Builder intake (cloud build)."
INTAKE_TEXT = (
    INTAKE_HEADER + " Plugin {v}. Commits from this build carry the cloud's own "
    "author name; the PR will be under the owner's name.\n\n"
    "Started from {sha}, the base commit the launch named."
)
INTAKE_ADOPT_TEXT = (
    INTAKE_HEADER + " Plugin {v}. Commits from this build carry the cloud's own "
    "author name; the PR will be under the owner's name.\n\n"
    "Continuing branch {branch} from {sha}, the pushed head the launch named."
)
DETECTIVE_INTAKE_TEXT = (
    "Detective intake (cloud session). Plugin {v}. This lane diagnoses only: it pushes no branch "
    "and opens no pull request, and its disposable copies live only inside this cloud session.\n\n"
    "Started from {sha}, the base commit the launch named."
)
DETECTIVE_INTAKE_ADOPT_TEXT = (
    "Detective intake (cloud session). Plugin {v}. This lane diagnoses only: it pushes no branch "
    "and opens no pull request, and its disposable copies live only inside this cloud session.\n\n"
    "Reading branch {branch} at {sha}, the pushed head the launch named."
)
HANDOVER_HEADER = "Builder handover (cloud build)."
HANDBACK_HEADER = "Builder handback (cloud build)."
STOP_HEADER = "Builder stop (cloud build)."
PARK_HEADER = "Builder park (cloud build)."
TERMINAL_HEADERS = {"handback": HANDBACK_HEADER, "stop": STOP_HEADER, "park": PARK_HEADER}
# deliberately not in TERMINAL_HEADERS: the newer lane's watch reads terminal headers created after its start, and a stand-down or a supersession notice is not the newer lane's ending
STAND_DOWN_HEADER = "Builder stand-down (cloud build)."
SUPERSEDED_HEADER = "Builder superseded (cloud build)."
CLOUD_FOOTER = "---\n_Generated by [Claude Code](https://claude.ai/code)_"  # the cloud harness appends it to every comment a cloud session posts
HANDOVER_FOOTER = "---\n_Generated by [Claude Code](https://claude.ai/code)_"  # the cloud harness appends it to every comment the builder posts
REFUSAL_HEADER = "Builder refusal (cloud build)."
REFUSAL_TEXT = {
    "plugin-version-mismatch": (
        "This cloud session runs plugin {running}; the launch named plugin {launched}. I built "
        "nothing. This lane ends as a refusal, and the advisor relaunches the build on the "
        "owner's machine."),
    "cloud-environment-mismatch": (
        "This cloud session's environment variable names {actual}; the launch named {expected}. "
        "I built nothing. This lane ends as a refusal."),
}
REFUSAL_OTHER = ("I could not start from the launch's base commit ({reason}). I built nothing. "
                 "This lane ends as a refusal.")
NOTE_HEADER = "Builder note for the advisor (cloud build)."
PROGRESS_HEADER = "Builder progress (cloud build)."
PROGRESS_EXPECTED_MAX_MINUTES = 240  # the longest wait a progress comment can state; the advisor never reads more
NOTE_CLOSING = "I'm waiting for your answer."
REVIEW_LAPSED_TEXT = (
    "Parked: the review did not run.\n\n"
    "The reviewer pass lapsed during this build, so no independent review happened. The work is "
    "pushed and this PR is not ready. It needs a fresh pass, then a review."
)


def _sibling(name):
    if _LIB_DIR not in sys.path:
        sys.path.insert(0, _LIB_DIR)
    return importlib.import_module(name)


_launch_lines = _sibling("launch_lines")  # the one home of the launch line labels
_VERSION_LINE = _launch_lines.line_regex(_launch_lines.VERSION, ".+")
_ENVIRONMENT_LINE = _launch_lines.line_regex(_launch_lines.ENVIRONMENT, ".+")
_BASE_LINE = _launch_lines.line_regex(_launch_lines.BASE, ".+")


def _env(env):
    return os.environ if env is None else env


def _git_env(env):
    """`env` with every GIT_* key removed and nothing else changed or added."""
    return {k: v for k, v in env.items() if not k.startswith("GIT_")}


def _call(run, argv, env, timeout):
    """(exit code, stdout) of one command; (None, "") when it could not run at all."""
    runner = subprocess.run if run is None else run
    try:
        proc = runner(list(argv), capture_output=True, text=True, timeout=timeout, env=env)
    except Exception:
        return None, ""
    code = getattr(proc, "returncode", None)
    out = getattr(proc, "stdout", "")
    return (code if isinstance(code, int) else None), (out if isinstance(out, str) else "")


def _git(run, repo_root, args, env, timeout=_GIT_TIMEOUT):
    return _call(run, ["git", "-C", repo_root] + list(args), env, timeout)


def _gh(run, args, env):
    return _call(run, ["gh"] + list(args), dict(env), _GH_TIMEOUT)


def _unique_line_value(lines, pattern):
    """The one value `pattern` captures across `lines`; None when absent or the lines disagree."""
    found = set()
    for line in lines:
        match = pattern.match(line)
        if match:
            found.add(match.group(1).strip())
    return found.pop() if len(found) == 1 else None


def _adopts_branch(lines):
    """(branch, head, invalid) from the `Adopts branch:` lines. An absent line is (None, None,
    False); a line that is not well formed (the launcher owns the format), or stated twice with
    different values, is (None, None, True)."""
    launcher = _sibling("launcher")
    found = set()
    for line in lines:
        if not line.startswith(launcher.ADOPTS_PREFIX):
            continue
        parsed = launcher.parse_adopts_line(line)
        if parsed is None:
            return None, None, True
        found.add(parsed)
    if not found:
        return None, None, False
    if len(found) > 1:
        return None, None, True
    branch, head = found.pop()
    return branch, head, False


def parse_launch(text):
    """advisorVersion, environment, baseCommit, adoptsBranch and adoptsHead from the launch prompt text; None
    for a line that is missing, malformed, or stated twice with different values. A malformed or
    conflicting `Adopts branch:` line is not read as missing: it adds `adoptsBranchInvalid: True`."""
    lines = [line.strip() for line in text.splitlines()] if isinstance(text, str) else []
    engine_adapter = _sibling("engine_adapter")
    environment = _unique_line_value(lines, _ENVIRONMENT_LINE)
    if environment is not None and not engine_adapter.CLOUD_ENVIRONMENT_ID_RE.fullmatch(environment):
        environment = None
    base = _unique_line_value(lines, _BASE_LINE)
    if base is not None and not _SHA_RE.match(base):
        base = None
    adopts, adopts_head, adopts_invalid = _adopts_branch(lines)
    parsed = {"advisorVersion": _unique_line_value(lines, _VERSION_LINE),
              "environment": environment, "baseCommit": base, "adoptsBranch": adopts,
              "adoptsHead": adopts_head}
    if adopts_invalid:
        parsed["adoptsBranchInvalid"] = True
    return parsed


def _refusal_comment(reason, running=None, launched=None, actual=None, expected=None):
    if reason == "plugin-version-mismatch":
        body = REFUSAL_TEXT[reason].format(running=running or "an unreadable version",
                                           launched=launched or "an unreadable version")
    elif reason == "cloud-environment-mismatch":
        body = REFUSAL_TEXT[reason].format(actual=actual or "no environment",
                                           expected=expected or "no environment")
    else:
        body = REFUSAL_OTHER.format(reason=reason)
    return REFUSAL_HEADER + "\n\n" + body


def refusal_versions(body):
    """(running, launched) a whole version-mismatch refusal comment (exactly `_refusal_comment`'s words) names; None for any other body."""
    match = isinstance(body, str) and re.search(r"plugin (\d+\.\d+\.\d+); the launch named plugin (\d+\.\d+\.\d+)\.", body.strip(), re.ASCII)
    return match.groups() if match and body.strip() == _refusal_comment("plugin-version-mismatch", *match.groups()) else None


def launch_charter(text):
    """`detective` when the launch text's first non-blank line is the launcher's detective command, else `workhorse`. Never raises."""
    if not isinstance(text, str):
        return "workhorse"
    first = next((line.strip() for line in text.splitlines() if line.strip()), None)
    return "detective" if first == _sibling("launcher")._CHARTER_COMMANDS["detective"] else "workhorse"


def _refused(reason, **named):
    return {"ok": False, "outcome": "refusal", "reason": reason, "startedFrom": None,
            "comment": _refusal_comment(reason, **named)}


def intake(repo_root, launch_text, *, env=None, run=None, running_version=None):
    """Check the launch against this session, then start from its base commit. Any failure is a
    refusal and nothing is checked out; steps 1-3 run no git command at all."""
    env = _env(env)
    launch = parse_launch(launch_text)
    if running_version is None:
        running_version = _sibling("launcher").plugin_version()
    launched = launch["advisorVersion"]
    running = (running_version if isinstance(running_version, str) and running_version.strip()
               else None)
    if running is None or launched is None or running != launched:
        return _refused("plugin-version-mismatch", running=running, launched=launched)

    cloud_pass = _sibling("cloud_pass")
    raw = env.get(cloud_pass.ENVIRONMENT_ENV)
    actual = raw.strip() if isinstance(raw, str) and raw.strip() else None
    expected = launch["environment"]
    if actual is not None and not _sibling("engine_adapter").CLOUD_ENVIRONMENT_ID_RE.fullmatch(actual):
        # Not an environment id: it is never printed, and it can never equal a launched id.
        actual, shown = None, "an unreadable environment"
    else:
        shown = actual
    if actual is None or expected is None or actual != expected:
        return _refused("cloud-environment-mismatch", actual=shown, expected=expected)

    sha = launch["baseCommit"]
    if sha is None:
        return _refused("base-commit-missing")
    detective = launch_charter(launch_text) == "detective"
    started_text = DETECTIVE_INTAKE_TEXT if detective else INTAKE_TEXT
    adopted_text = DETECTIVE_INTAKE_ADOPT_TEXT if detective else INTAKE_ADOPT_TEXT

    history = ensure_history(repo_root, env=env, run=run)
    if not history["ok"]:
        return _refused("history-unfetchable")

    genv = _git_env(env)
    code, _ = _git(run, repo_root, ["fetch", "origin", sha], genv)
    if code != 0:
        return _refused("base-commit-unfetchable")
    code, _ = _git(run, repo_root, ["cat-file", "-e", sha + "^{commit}"], genv)
    if code != 0:
        return _refused("base-commit-unfetchable")

    # axis: a launch whose adopt line is malformed or conflicting is refused before any checkout, never read as a launch with no adopt line
    if launch.get("adoptsBranchInvalid"):
        return _refused("adopts-branch-invalid")
    branch = launch["adoptsBranch"]
    if branch is None:
        code, _ = _git(run, repo_root, ["checkout", "--detach", sha], genv)
        if code != 0:
            return _refused("base-checkout-failed")
        return {"ok": True, "outcome": None, "reason": None, "startedFrom": sha, "branch": None,
                "comment": started_text.format(v=running, sha=sha), "pluginVersion": running}

    head = launch["adoptsHead"]
    tracking = "refs/remotes/origin/%s" % branch
    # axis: a single-branch clone maps only its first branch, and git sets an upstream only on a mapped remote-tracking ref — so the adopted branch is mapped before it is fetched
    code, _ = _git(run, repo_root, ["remote", "set-branches", "--add", "origin", branch], genv)
    if code != 0:
        return _refused("adopted-branch-unfetchable")
    code, _ = _git(run, repo_root, ["fetch", "origin", "+refs/heads/%s:%s" % (branch, tracking)],
                   genv)
    if code != 0:
        return _refused("adopted-branch-unfetchable")
    code, tip = _git(run, repo_root, ["rev-parse", "--verify", tracking], genv)
    # axis: the adopted branch's remote tip must equal the adopted head the launch named — a branch that moved since the launch was composed is refused, never continued; the base commit is the stack gate's and may be a lower layer's head — see bite-proof record adopt_branch
    if code != 0 or tip.strip() != head:
        return _refused("adopted-branch-moved")
    # axis: the adopted head must descend from the base commit — a branch unrelated to the base the launch named is refused, never continued
    code, _ = _git(run, repo_root, ["merge-base", "--is-ancestor", sha, head], genv)
    if code != 0:
        return _refused("adopted-head-not-on-base")
    code, _ = _git(run, repo_root, ["checkout", "-B", branch, head], genv)
    if code != 0:
        return _refused("base-checkout-failed")
    code, _ = _git(run, repo_root, ["branch", "--set-upstream-to=origin/%s" % branch, branch],
                   genv)
    if code != 0:
        return _refused("adopted-branch-upstream-failed")
    return {"ok": True, "outcome": None, "reason": None, "startedFrom": head, "branch": branch,
            "comment": adopted_text.format(v=running, sha=head, branch=branch),
            "pluginVersion": running}


def _shallow_answer(git):
    code, out = git(["rev-parse", "--is-shallow-repository"])
    answer = out.strip() if code == 0 else None
    return answer if answer in ("true", "false") else None


def ensure_history(repo_root, *, main_branch="main", env=None, run=None, budget=None):
    """Make the clone's history complete and fetch origin/<main_branch>. Idempotent: on a full
    clone it still fetches the branch, which changes nothing. `budget` (seconds, None = each
    command keeps its own limit) bounds the whole preparation: every git command gets the time
    left, capped at the per-command limit, and a spent budget ends it as "budget-exhausted"."""
    genv = _git_env(_env(env))
    fetched = []
    deadline = None if budget is None else time.monotonic() + budget

    def git(args):
        if deadline is None:
            return _git(run, repo_root, args, genv)
        left = deadline - time.monotonic()
        if left <= 0:
            return None, ""
        return _git(run, repo_root, args, genv, min(_GIT_TIMEOUT, left))

    def result(reason):
        return {"ok": reason is None, "reason": reason, "fetched": fetched}

    shallow = _shallow_answer(git)
    if shallow is None:
        return result("shallow-state-unreadable")
    if shallow == "true":
        code, _ = git(["fetch", "--unshallow", "origin"])
        if code != 0:
            return result("unshallow-failed")
        fetched.append("unshallow")
    ref = "refs/remotes/origin/%s" % main_branch
    code, _ = git(["fetch", "origin", "+refs/heads/%s:%s" % (main_branch, ref)])
    if code != 0:
        return result("main-fetch-failed")
    fetched.append("origin/%s" % main_branch)
    code, _ = git(["rev-parse", "--verify", "--quiet", ref])
    if code != 0 or _shallow_answer(git) != "false":
        return result("history-still-incomplete")
    return result(None)


def github_channel(gh_probe, tools_write):
    """The channel the builder can write through: gh when its probe passed by a sign-in check,
    else the session's GitHub tools when the builder's own write through them worked, else none.
    A probe that passed only by a REST read (`channel: "rest"`) proves no write, so it never
    selects gh."""
    if (isinstance(gh_probe, dict) and gh_probe.get("ok") is True
            and gh_probe.get("channel") != "rest"):
        return {"ok": True, "channel": "gh"}
    if tools_write == "ok":
        return {"ok": True, "channel": "tools"}
    return {"ok": False, "channel": None, "reason": "no-github-channel"}


def _json_object_or_list(text):
    try:
        return json.loads(text)
    except ValueError:
        return None


def _pull_fields(pull):
    """The `gh pr view --json` fields from one REST pull object; None when it is malformed."""
    if not isinstance(pull, dict):
        return None
    user = pull.get("user") if isinstance(pull.get("user"), dict) else {}
    head = pull.get("head") if isinstance(pull.get("head"), dict) else {}
    base = pull.get("base") if isinstance(pull.get("base"), dict) else {}
    number = pull.get("number")
    if isinstance(number, bool) or not isinstance(number, int):
        return None
    body = pull.get("body")
    return {"number": number, "title": pull.get("title"), "author": {"login": user.get("login")},
            "headRefName": head.get("ref"), "headRefOid": head.get("sha"),
            "baseRefName": base.get("ref"), "url": pull.get("html_url"),
            "body": "" if body is None else body}


def pr_json(repo, branch, *, run=None, env=None):
    """The one open pull request whose head is `branch`, in `gh pr view --json` field names."""
    env = _env(env)
    if not (isinstance(repo, str) and _REPO_RE.match(repo) and isinstance(branch, str) and branch):
        return {"ok": False, "reason": "github-read-failed"}
    owner = repo.split("/", 1)[0]
    endpoint = "repos/%s/pulls?head=%s:%s&state=open" % (repo, owner, urllib.parse.quote(branch, safe="/"))
    code, out = _gh(run, ["api", endpoint], env)
    pulls = _json_object_or_list(out) if code == 0 else None
    if not isinstance(pulls, list):
        return {"ok": False, "reason": "github-read-failed"}
    if not pulls:
        return {"ok": False, "reason": "pr-not-found"}
    if len(pulls) > 1:
        return {"ok": False, "reason": "pr-ambiguous"}
    pr = _pull_fields(pulls[0])
    if pr is None:
        return {"ok": False, "reason": "github-read-failed"}
    return {"ok": True, "pr": pr}


def repo_json(repo, *, run=None, env=None):
    """The repository's name with owner, as GitHub spells it."""
    env = _env(env)
    if not (isinstance(repo, str) and _REPO_RE.match(repo)):
        return {"ok": False, "reason": "github-read-failed"}
    code, out = _gh(run, ["api", "repos/%s" % repo, "--jq", ".full_name"], env)
    if code != 0 or not out.strip():
        return {"ok": False, "reason": "github-read-failed"}
    return {"ok": True, "nameWithOwner": out.strip()}


def post_comment(repo, number, body_path, *, run=None, env=None):
    """Exactly one comment write on an issue or pull request; never loops or batches."""
    env = _env(env)
    failed = {"ok": False, "reason": "github-write-failed", "url": None}
    if not (isinstance(repo, str) and _REPO_RE.match(repo)
            and isinstance(number, int) and not isinstance(number, bool) and number > 0
            and isinstance(body_path, str) and body_path):
        return failed
    code, out = _gh(run, ["api", "-X", "POST", "repos/%s/issues/%d/comments" % (repo, number),
                          "-F", "body=@%s" % body_path], env)
    if code != 0:
        return failed
    posted = _json_object_or_list(out)
    url = posted.get("html_url") if isinstance(posted, dict) else None
    return {"ok": True, "reason": None, "url": url if isinstance(url, str) else None}


def edit_comment(repo, comment_id, body_path, *, run=None, env=None):
    """Exactly one write that replaces an existing comment's body in place; never loops or batches."""
    env = _env(env)
    failed = {"ok": False, "reason": "github-write-failed", "url": None}
    if not (isinstance(repo, str) and _REPO_RE.match(repo)
            and isinstance(comment_id, int) and not isinstance(comment_id, bool) and comment_id > 0
            and isinstance(body_path, str) and body_path):
        return failed
    code, out = _gh(run, ["api", "-X", "PATCH", "repos/%s/issues/comments/%d" % (repo, comment_id),
                          "-F", "body=@%s" % body_path], env)
    if code != 0:
        return failed
    edited = _json_object_or_list(out)
    url = edited.get("html_url") if isinstance(edited, dict) else None
    return {"ok": True, "reason": None, "url": url if isinstance(url, str) else None}


def note_text(question):
    """The builder's note to the advisor, as comment text."""
    return {"comment": "%s\n\n%s\n\n%s" % (NOTE_HEADER, question.strip(), NOTE_CLOSING)}


def _one_line(value):
    """True when `value` is a string with text in it and no line break."""
    return isinstance(value, str) and bool(value.strip()) and "\n" not in value and "\r" not in value


def progress_text(phase, running, started_at, expected_minutes, lost=None):
    """The progress comment the builder keeps on its issue, as comment text; a refusal is a result, never a raise."""
    if not _one_line(phase):
        return {"ok": False, "reason": "phase-invalid"}
    if not _one_line(running):
        return {"ok": False, "reason": "running-invalid"}
    if not (isinstance(started_at, str) and _STARTED_RE.match(started_at)):
        return {"ok": False, "reason": "started-invalid"}
    try:
        datetime.datetime.strptime(started_at, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return {"ok": False, "reason": "started-invalid"}
    if (isinstance(expected_minutes, bool) or not isinstance(expected_minutes, int)
            or not 1 <= expected_minutes <= PROGRESS_EXPECTED_MAX_MINUTES):
        return {"ok": False, "reason": "expected-invalid"}
    if isinstance(lost, str) and ("\n" in lost or "\r" in lost):
        return {"ok": False, "reason": "lost-invalid"}
    lines = [PROGRESS_HEADER, "", "Phase: " + phase.strip(), "Now running: " + running.strip(),
             "Started: " + started_at.strip(), "Expected: %d minutes" % expected_minutes]
    if isinstance(lost, str) and lost.strip():
        lines.append("Lost work: " + lost.strip())
    return {"ok": True, "comment": "\n".join(lines)}


def _progress_field(lines, label):
    """The stripped value of the first `label` line; None when there is none or it is blank."""
    for line in lines:
        if line.startswith(label):
            return line[len(label):].strip() or None
    return None


def parse_progress(body):
    """The fields of a progress comment (as `progress_text` writes it, with or without the cloud footer); None
    for any other body. `expectedSeconds` is never more time than the comment states, nor more than the cap:
    a missing or malformed `Expected:` line reads as 0."""
    text = strip_cloud_footer(body)
    if text is None or text.split("\n", 1)[0].rstrip() != PROGRESS_HEADER:
        return None
    lines = text.split("\n")[1:]
    expected = 0
    for line in lines:
        if line.startswith("Expected:"):
            match = _EXPECTED_RE.match(line)
            if match:
                digits = match.group(1).lstrip("0") or "0"
                minutes = int(digits) if len(digits) <= 9 else PROGRESS_EXPECTED_MAX_MINUTES
                expected = min(minutes, PROGRESS_EXPECTED_MAX_MINUTES) * 60
            break
    return {"phase": _progress_field(lines, "Phase:"), "running": _progress_field(lines, "Now running:"),
            "startedAt": _progress_field(lines, "Started:"), "expectedSeconds": expected,
            "lostWork": _progress_field(lines, "Lost work:")}


def review_lapsed_text():
    """The park comment for a reviewer pass that lapsed before the review ran."""
    return {"comment": REVIEW_LAPSED_TEXT}


def handover_text(sha):
    """The handover comment naming the pushed head; None when `sha` is not 40 lowercase hex."""
    if not isinstance(sha, str) or not _SHA_RE.fullmatch(sha):
        return None
    return (HANDOVER_HEADER + "\n\nI pushed my work and stopped working on this issue. "
            "My pushed head is " + sha + ".")


def handover_sha(body):
    """The pushed head a whole handover comment names: exactly `handover_text`'s words, optionally followed on
    a later line by the cloud harness's one `HANDOVER_FOOTER`; None for any other body."""
    if not isinstance(body, str):
        return None
    text = body.strip()
    if text.endswith("\n" + HANDOVER_FOOTER):
        text = text[:-len(HANDOVER_FOOTER)].rstrip()
    match = re.search(r"([0-9a-f]{40})\.$", text)
    return match.group(1) if match and text == handover_text(match.group(1)) else None


def terminal_text(kind, text):
    """The handback, stop or park comment: the kind's fixed header, then `text`. A refusal is a result."""
    if kind not in TERMINAL_HEADERS:
        return {"ok": False, "reason": "kind-invalid"}
    if not isinstance(text, str) or not text.strip():
        return {"ok": False, "reason": "text-empty"}
    return {"ok": True, "comment": TERMINAL_HEADERS[kind] + "\n\n" + text.strip()}


def strip_cloud_footer(body):
    """`body` trimmed, less one trailing cloud footer on its own line; None when `body` is not a string."""
    if not isinstance(body, str):
        return None
    text = body.strip()
    if text.endswith("\n" + CLOUD_FOOTER):
        text = text[:-len("\n" + CLOUD_FOOTER)].rstrip()
    return text


def terminal_kind(body):
    """Which builder comment `body` is: "handback", "stop", "park", "handover", or None for any other."""
    text = strip_cloud_footer(body)
    if text is None:
        return None
    # handover_sha strips its own one footer, so it reads the raw body: a second footer is never dropped here
    if handover_sha(body) is not None:
        return "handover"
    first = text.split("\n", 1)[0].rstrip()
    for kind, header in TERMINAL_HEADERS.items():
        if first == header:
            return kind
    return None


def stand_down_text(url):
    """The comment a superseded builder posts when it wakes: it names the newer launch's comment and says
    the session pushed nothing after waking."""
    return (STAND_DOWN_HEADER + "\n\nA newer launch took this issue over (its supersession notice: " + url + "). "
            "This session stopped when it woke: it pushed nothing after waking and will push nothing more.")


def superseded_notice_text(launch_id):
    """The notice the advisor posts on the issue before it launches any successor; None when `launch_id` is
    not one line of text."""
    if not _one_line(launch_id):
        return None
    return (SUPERSEDED_HEADER + "\n\nThe advisor is launching a successor for this issue; the earlier lane "
            + launch_id.strip() + " is superseded. A cloud builder of an earlier lane that wakes stops without pushing.")


def _opens_with(body, *headers):
    """True when `body`, its footer and leading whitespace stripped, starts with one of `headers`."""
    text = strip_cloud_footer(body)
    return text is not None and text.lstrip().startswith(headers)


def _positive_int(value):
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def superseded(repo, issue, started, *, env=None, run=None):
    """Whether a newer launch took the issue over since the builder started: a supersession notice created
    later than `started` (the builder's own start time, UTC ISO). Intake comments never order launches: a
    delayed intake post must not reverse which builder is superseded. `newerLaunch` names the newest such
    notice. A refusal is a result, never a raise."""
    cloud_recover = _sibling("cloud_recover")
    started_at = cloud_recover._epoch(started)
    # axis: every input is judged before any read, so no GitHub call runs on an argument the verb never checked — see bite-proof record i2272_stand_down
    if not (isinstance(repo, str) and _REPO_RE.match(repo) and _positive_int(issue) and started_at is not None):
        return {"ok": False, "reason": "input-invalid"}
    # the contract reads from `since - 1`, so 1 asks for every comment from epoch 0 on
    comments = cloud_recover._issue_comments(repo, issue, 1, _env(env), run)
    # axis: the comments are read whole, or no newer launch is ruled out — a failed read is a refusal, never an empty issue — see bite-proof record i2272_stand_down
    if comments is None:
        return {"ok": False, "reason": "comments-unreadable"}
    stamped = []
    for comment in comments:
        created = cloud_recover._epoch(comment.get("created_at"))
        if created is not None and _positive_int(comment.get("id")):
            stamped.append((created, comment["id"], comment))
    # axis: a newer launch is shown only by a supersession notice created later than the builder's start, never by an intake comment — see bite-proof record i2272_stand_down
    newer = [(created, cid, comment) for created, cid, comment in stamped
             if created > started_at and _opens_with(comment.get("body"), SUPERSEDED_HEADER)]
    if not newer:
        return {"ok": True, "superseded": False, "newerLaunch": None, "comment": None}
    _, cid, comment = max(newer, key=lambda t: (t[0], t[1]))
    url = comment.get("html_url")
    if not isinstance(url, str) or not url:
        url = "https://github.com/%s/issues/%d#issuecomment-%d" % (repo, issue, cid)
    return {"ok": True, "superseded": True,
            "newerLaunch": {"commentId": cid, "url": url, "createdAt": comment["created_at"]},
            "comment": stand_down_text(url)}


def pass_state(env=None, now=None):
    """The placed reviewer sign-in's state and lapse date, and whether this is a cloud session."""
    env = _env(env)
    cloud_pass = _sibling("cloud_pass")
    out = cloud_pass.placed_pass_state(env=env, now=now)
    out["cloud"] = cloud_pass._is_cloud(env)
    return out


def _read_text(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, ValueError):
        return None


def _write_json_atomic(path, value):
    tmp = "%s.tmp-%d" % (path, os.getpid())
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(value, fh)
    os.replace(tmp, path)


def _gh_probe_from(path):
    text = _read_text(path)
    probe = _json_object_or_list(text) if text is not None else None
    return probe if isinstance(probe, dict) else {}


def _build_parser():
    parser = argparse.ArgumentParser(prog="cloud_builder.py")
    verbs = parser.add_subparsers(dest="verb", required=True)

    def verb(name, *options, **choices):
        sub = verbs.add_parser(name)
        for option in options:
            sub.add_argument(option, required=True, **choices.get(option, {}))
        return sub

    verb("intake", "--repo-root", "--launch-file")
    verb("ensure-history", "--repo-root").add_argument("--main-branch", default="main")
    verb("github-channel", "--gh-probe-file", "--tools-write",
         **{"--tools-write": {"choices": ["ok", "failed", "not-tried"]}})
    verb("pr-json", "--repo", "--branch", "--out")
    verb("repo-json", "--repo")
    verb("post", "--repo", "--number", "--body-file", **{"--number": {"type": int}})
    verb("edit", "--repo", "--comment-id", "--body-file", **{"--comment-id": {"type": int}})
    verb("progress", "--phase", "--running", "--started", "--expected-minutes",
         **{"--expected-minutes": {"type": int}}).add_argument("--lost", default=None)
    verb("note", "--question-file")
    verb("review-lapsed")
    verb("handover", "--head")
    verb("terminal", "--kind", "--text-file", **{"--kind": {"choices": ["handback", "stop", "park"]}})
    verb("pass-state")
    verb("superseded", "--repo", "--issue", "--started", **{"--issue": {"type": int}})
    verb("superseded-notice", "--launch-id")
    return parser


def _dispatch(args):
    if args.verb == "intake":
        return intake(args.repo_root, _read_text(args.launch_file) or "")
    if args.verb == "ensure-history":
        return ensure_history(args.repo_root, main_branch=args.main_branch)
    if args.verb == "github-channel":
        return github_channel(_gh_probe_from(args.gh_probe_file), args.tools_write)
    if args.verb == "pr-json":
        result = pr_json(args.repo, args.branch)
        if result["ok"]:
            try:
                _write_json_atomic(args.out, result["pr"])
            except OSError:
                return {"ok": False, "reason": "output-unwritable"}
        return result
    if args.verb == "repo-json":
        return repo_json(args.repo)
    if args.verb == "post":
        return post_comment(args.repo, args.number, args.body_file)
    if args.verb == "edit":
        return edit_comment(args.repo, args.comment_id, args.body_file)
    if args.verb == "progress":
        return progress_text(args.phase, args.running, args.started, args.expected_minutes, args.lost)
    if args.verb == "note":
        question = _read_text(args.question_file)
        if question is None:
            return {"ok": False, "reason": "question-unreadable"}
        return note_text(question)
    if args.verb == "review-lapsed":
        return review_lapsed_text()
    if args.verb == "handover":
        comment = handover_text(args.head)
        if comment is None:
            return {"ok": False, "reason": "head-invalid"}
        return {"ok": True, "comment": comment}
    if args.verb == "terminal":
        text = _read_text(args.text_file)
        if text is None:
            return {"ok": False, "reason": "text-unreadable"}
        return terminal_text(args.kind, text)
    if args.verb == "superseded":
        return superseded(args.repo, args.issue, args.started)
    if args.verb == "superseded-notice":
        comment = superseded_notice_text(args.launch_id)
        if comment is None:
            return {"ok": False, "reason": "input-invalid"}
        return {"ok": True, "comment": comment}
    return pass_state()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as exc:
        result = {"ok": False, "reason": "usage"}
        sys.stdout.write(json.dumps(result) + "\n")
        return 0 if exc.code == 0 else 1
    result = _dispatch(args)
    sys.stdout.write(json.dumps(result) + "\n")
    return 1 if result.get("ok") is False else 0


if __name__ == "__main__":
    sys.exit(main())
