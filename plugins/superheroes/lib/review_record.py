#!/usr/bin/env python3
"""The review record: one marker-tagged PR comment per review session, decided in one place.

A write only creates. It adds one new record comment, plus one new comment per raw reviewer output
file, and never edits a comment. The record links the record before it (previousRecord) and each raw
comment (rawOutputs), so everything stays retrievable. The one thing a write reads from an earlier
record is the identity key of each finding in the latest one (_unaccounted): every such key must
appear in the new account's findings with an outcome, or the write refuses before anything is posted.
An earlier record that cannot be parsed never blocks a write. Every earlier record that could not be
parsed or was changed in transit is listed on each new record (earlierRecordsNotChecked), so the vet
reads those directly however many records came after them.

build_record() is the only place a status, a reviewer's ran-state or a code fact is decided;
write() is the only path that posts, and read() does I/O only. Facts that code holds (lane, final
commit, CI, whether a reviewer with a run directory ran on the final commit) come from code, never
from the session's account.

CLI:
  review_record.py write --account FILE --repo-root DIR
  review_record.py read --pr N [--repo OWNER/NAME]
  review_record.py reading-next --run-dir A [--run-dir B] [--seat-map FILE] --maker-family F [--maker-family F ...]

In a cloud session (CLAUDE_CODE_REMOTE is "true") the repo, PR and issue reads go through `gh api` REST, and the
closing issue comes from the first line of the PR body.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import build_lane  # noqa: E402
import cloud_pass  # noqa: E402
import command_refusals  # noqa: E402
import finding_outcomes  # noqa: E402
import gh_pages  # noqa: E402
import lane_call  # noqa: E402
import model_registry  # noqa: E402
import pr_comment  # noqa: E402
import review_findings_schema as rfs  # noqa: E402
import sanitized_view  # noqa: E402
import seat_map as seat_map_module  # noqa: E402
import session_contract  # noqa: E402
import stack_check  # noqa: E402
import store_core  # noqa: E402

MARKER = "<!-- superheroes:review-record -->"
RAW_MARKER = "<!-- superheroes:review-raw-output -->"
# A part comment holds one slice of a record's JSON text. It must never start with MARKER: a part is not a record.
PART_MARKER = "<!-- superheroes:review-record-part -->"
PARTS_SCHEMA = "review-record-parts/1"
CAP_KINDS = ("rounds", "ceiling")
CARRIED_SETTLED = ("fixed", "applies", "unsettled")
ACCOUNT_SCHEMA = "review-account/1"
RECORD_SCHEMA = "review-record/1"
FORBIDDEN_CLAIMS = ("no bugs", "bug-free", "bug free")
MAX_BODY_CHARS = 65000
GITHUB_MAX_CHARS = 65536
SESSION = "reported by the session"
# The reviewer ran-state vocabulary, its one home: the sheet builder validates against RAN_STATES; the sheet
# schema holds no copy of it (a test pins that).
RAN_ENGINE_RECORD = "engine-record"
RAN_REPORTED_BY_SESSION = "reported-by-session"
RAN_NOT_RUN = "not-run"
RAN_STATES = (RAN_ENGINE_RECORD, RAN_REPORTED_BY_SESSION, RAN_NOT_RUN)
# The reasons a planned seat is named as not run without being a missing review, its one home: token -> (the only
# seat name it may label, the words the record carries). The writer refuses the token on any other row, and the
# session's account and a hand-written one both name the seat through it.
NOT_RUN_REASONS = {"no-loop-phase": (seat_map_module.GROUNDING_SEAT,
                                     "no loop phase runs it, so no reviewer checked the PR body's claims")}
_LEFT_FOR_OWNER = rfs.LEFT_FOR_OWNER
_RULING = rfs.OUTCOMES[-1]
_RED = frozenset({"failure", "timed_out", "cancelled", "action_required", "startup_failure", "stale"})
# GitHub lists at most 3000 files for a pull request; a list this long may be cut short.
_FILES_CEILING = 3000
# The review lane vocabulary: its one home is lane_call.LANES. The lane matcher below is built from it and the
# sheet builder validates against this alias of it; the sheet schema holds no copy of it (a test pins that).
LANES = lane_call.LANES
_LANE_RE = re.compile(
    r"(?m)^\*\*Lane call:\*\*\s*(" + "|".join(re.escape(lane) for lane in LANES) + r")\b[.:]?[ \t]*(.*)$"
)
_REPO_RE = re.compile(r"[^/\s]+/[^/\s]+")
_CLOSES_RE = stack_check.CLOSES_RE
_REASON_LEAD_RE = re.compile(r"^[\s,;:—–-]+")
_VENDOR_MODELS = {"claude": model_registry.claude_models, "codex": model_registry.codex_models,
                  "cursor": model_registry.cursor_models}


# The words of the record's optional parts, their one home.
GRADE_VERDICTS = ("confirmed", "plausible", "wrong")
RUN_STATUSES = ("ran", "timed-out", "not-started")
SOURCE_KINDS = ("reviewer", "sweep")
# The optional account keys the record carries whole, when the account has them.
_ROUND_PARTS = ("rerunChecks", "synthesisRounds", "outsideThisPR", "unreadShare")


class Refusal(Exception):
    def __init__(self, reason, detail):
        super().__init__(reason, detail)
        self.reason, self.detail = reason, detail


def _refuse(reason, detail):
    return {"ok": False, "reason": reason, "detail": detail}


# --- default readers: each wraps a tool and never raises; an error becomes None ---

def _run(argv, cwd=None):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=60, cwd=cwd)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def _is_ancestor(repo_root, commit, head):
    """True when `commit` is in `head`'s history, False when it is not, None when git could not say.

    Not _run: that folds exit 1 (not an ancestor) and a real error into one None.
    """
    if not (isinstance(repo_root, str) and os.path.isdir(repo_root)) \
            or not all(isinstance(x, str) and x and not x.startswith("-") for x in (commit, head)):
        return None
    try:
        r = subprocess.run(["git", "-C", repo_root, "merge-base", "--is-ancestor", commit, head],
                           capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return {0: True, 1: False}.get(r.returncode)


def _gh_json(*args):
    out = _run(["gh", *args])
    try:
        return None if out is None else json.loads(out)
    except ValueError:
        return None


def _read_pages(path, key=None):
    """Every row of a GitHub REST list by page number (gh_pages.read), or None."""
    return gh_pages.read(lambda endpoint: _run(["gh", "api", endpoint]), path, key=key)


def _repo_name(repo_root):
    out = _run(["gh", "repo", "view", "--json", "nameWithOwner"], cwd=repo_root)
    try:
        name = None if out is None else json.loads(out).get("nameWithOwner")
    except (ValueError, AttributeError):
        return None
    return name if isinstance(name, str) and _REPO_RE.fullmatch(name) else None


def _read_text(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except (OSError, ValueError):  # ValueError covers UnicodeDecodeError
        return None


def _api(repo, tail):
    return "repos/" + (repo or "{owner}/{repo}") + "/" + tail


def _pr_meta(pr, repo):
    d = _gh_json("pr", "view", str(pr), "--json", "headRefOid,body,closingIssuesReferences",
                 *(["--repo", repo] if repo else []))
    try:
        refs = [i["number"] for i in d.get("closingIssuesReferences") or [] if isinstance(i, dict)]
        return {"head": d["headRefOid"], "body": d.get("body") or "", "issues": refs}
    except (KeyError, TypeError, AttributeError):
        return None


def _issue_body(n, repo):
    d = _gh_json("issue", "view", str(n), "--json", "body", *(["--repo", repo] if repo else []))
    return d.get("body") if isinstance(d, dict) else None


def _repo_name_rest(repo_root):
    out = _run(["gh", "api", "repos/{owner}/{repo}", "--jq", ".full_name"], cwd=repo_root)
    name = None if out is None else out.strip()
    return name if name and _REPO_RE.fullmatch(name) else None


def _closing_issues(body, repo):
    """The issue numbers the PR body's first line closes, in order, duplicates removed; anything else reads as none."""
    if not isinstance(body, str):
        return []
    first = body.split("\n", 1)[0].removesuffix("\r")
    found = []
    for m in _CLOSES_RE.finditer(first):
        n = int(m.group(2))
        if n > 0 and n not in found and (m.group(1) is None or m.group(1).lower() == (repo or "").lower()):
            found.append(n)
    return found


closing_issues = _closing_issues


def _pr_meta_rest(pr, repo):
    d = _gh_json("api", _api(repo, f"pulls/{pr}"))
    try:
        body = d.get("body") or ""
        return {"head": d["head"]["sha"], "body": body, "issues": _closing_issues(body, repo)}
    except (KeyError, TypeError, AttributeError):
        return None


def _issue_body_rest(n, repo):
    d = _gh_json("api", _api(repo, f"issues/{n}"))
    return d.get("body") if isinstance(d, dict) else None


def _check_data(sha, repo):
    base = _api(repo, f"commits/{sha}")
    # Every page, merged: a failed page read leaves CI unavailable, never green on a partial read.
    rows = _read_pages(base + "/check-runs", key="check_runs")
    status = _gh_json("api", base + "/status")
    runs = None if rows is None else {"check_runs": rows}
    # The workflow runs on the head: which workflow ran is what a declared CI workflow is read against.
    wf_rows = _read_pages(_api(repo, f"actions/runs?head_sha={sha}"), key="workflow_runs")
    if runs is None or not isinstance(status, dict) or wf_rows is None \
            or not all(isinstance(row, dict) for row in wf_rows):
        return None
    # Only a run of this exact commit counts; a row with no head_sha does not.
    return runs, status, {"workflow_runs": [row for row in wf_rows if row.get("head_sha") == sha]}


def _ci_workflow(repo_root):
    """The project's declared CI workflow as (kind, name): "declared" with the workflow's name, "absent"
    when the profile holds no declaration, "unreadable" when it could not be read whole. Never raises,
    never writes: a declaration that cannot be read is never read as an absent one."""
    try:
        if repo_root is None:
            return ("unreadable", None)
        import core_md
        import project_config

        path = core_md.core_path(repo_root, None, persist_backfill=False)
        if core_md.read(repo_root, None, persist_backfill=False) is None:
            if core_md.gate_config_is_absent(core_md._classify_core_md_at_path(path)):
                return ("absent", None)
            return ("unreadable", None)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
        block = json.loads(core_md._JSON_BLOCK.search(text).group(1))
        config = block.get(core_md.PROJECT_CONFIGURATION_KEY)
        if config is None:
            return ("absent", None)
        if not isinstance(config, dict):
            return ("unreadable", None)
        if project_config.CI_WORKFLOW_SLUG not in config:
            return ("absent", None)
        got = project_config.get_item(
            repo_root, project_config.CI_WORKFLOW_SLUG, persist_backfill=False)
        value = got.get("effective")
        if got.get("malformed") is True or not isinstance(value, str) or not value.strip():
            return ("unreadable", None)
        return ("declared", value.strip())
    except Exception:
        return ("unreadable", None)


def _lane_marker(repo_root):
    try:
        branch = _run(["git", "-C", repo_root, "rev-parse", "--abbrev-ref", "HEAD"]).strip()
        with open(build_lane._marker_path(repo_root), encoding="utf-8") as fh:
            marker = json.load(fh)
        return dict(marker, currentBranch=branch)
    except (AttributeError, TypeError, OSError, ValueError, store_core.RepoRootUnavailable):
        return None


def _engine_run(run_dir):
    try:
        import engine_dispatch
        return engine_dispatch.run_execution_record(run_dir)
    except Exception:
        return None, "engine-unavailable"


def _list_comments(pr, repo):
    rows = _read_pages(_api(repo, f"issues/{pr}/comments"))
    try:
        return None if rows is None else [
            {"id": c["id"], "author": c["user"]["login"], "body": c["body"], "url": c["html_url"]}
            for c in rows]
    except (ValueError, KeyError, TypeError):
        return None


def changed_paths(pr, repo):
    """Every path the PR changes, as a list, or None when the list cannot be trusted to be complete:
    a failed call or parse, an entry with no string filename, or GitHub's file ceiling reached.
    Removed files are kept (a deletion inside a risk area touches it), and so is each renamed
    file's previous name (a rename out of a risk area still touches it)."""
    files = _read_pages(_api(repo, f"pulls/{pr}/files"))
    # axis: a file list that may be cut short is unavailable, never read as the whole change — see bite-proof record wo_a_1795_lane-call
    if files is None or len(files) >= _FILES_CEILING:
        return None
    paths = []
    for f in files:
        if not isinstance(f, dict) or not isinstance(f.get("filename"), str):
            return None
        paths.append(f["filename"])
        previous = f.get("previous_filename")
        if previous is not None and not isinstance(previous, str):
            return None
        # axis: a renamed file's previous path counts as changed, so a rename out of an area touches it — see bite-proof record wo_a_1795_lane-call
        if previous is not None:
            paths.append(previous)
    return paths


def _send(method, path, body):
    fd, tmp = tempfile.mkstemp(suffix=".md")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(body)
        d = _gh_json("api", "-X", method, path, "-F", f"body=@{tmp}")
    finally:
        os.unlink(tmp)
    return {"id": d["id"], "url": d.get("html_url")} if isinstance(d, dict) and "id" in d else None


def _owner_ruling_comment(repo, comment_id):
    """One issue comment as GitHub returns it (plain REST, so it works in a cloud session too), or None."""
    doc = _gh_json("api", f"repos/{repo}/issues/comments/{comment_id}")
    return doc if isinstance(doc, dict) else None


def _create_comment(pr, repo, body):
    return _send("POST", _api(repo, f"issues/{pr}/comments"), body)


def _withheld_paths(repo_root, head_sha, paths):
    """The changed paths no external reviewer could read in full, from the one rule that builds the view."""
    return sanitized_view.withheld_review_paths(repo_root, head_sha, paths)


def _readers(overrides):
    cloud = cloud_pass._is_cloud(os.environ)
    return {"pr_meta": _pr_meta_rest if cloud else _pr_meta, "issue_body": _issue_body_rest if cloud else _issue_body,
            "check_data": _check_data, "ci_workflow": _ci_workflow,
            "lane_marker": _lane_marker, "engine_run": _engine_run, "list_comments": _list_comments,
            "create_comment": _create_comment, "repo_name": _repo_name_rest if cloud else _repo_name,
            "read_text": _read_text, "is_ancestor": _is_ancestor,
            "changed_paths": changed_paths, "withheld_paths": _withheld_paths, "decision_sources": finding_outcomes.decision_sources,
            "owner_ruling_comment": _owner_ruling_comment,
            **(overrides or {})}


# --- the account ---

def _wider_ok(wider):
    """``rounds.wider`` is a list of ``{round, why}``: an integer round and a non-blank reason."""
    return isinstance(wider, list) and all(
        isinstance(w, dict) and isinstance(w.get("round"), int) and not isinstance(w["round"], bool)
        and isinstance(w.get("why"), str) and bool(w["why"].strip()) for w in wider)


def _step_ok(v):
    return v is None or (isinstance(v, int) and not isinstance(v, bool))


def _makers_for(makers, step):
    """Families that were makers of what a reviewer at `step` reviewed: a maker with a `fromStep` joined
    only after earlier steps, so a reviewer before that step is judged against the makers it faced. A
    reviewer with no step, or a maker with no `fromStep`, counts in full."""
    return frozenset(m["family"] for m in makers
                     if m.get("fromStep") is None or step is None or step >= m["fromStep"])


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _nb(v):
    return isinstance(v, str) and bool(v.strip())


def _nb_or_none(v):
    return v is None or _nb(v)


def _str_or_none(v):
    return v is None or isinstance(v, str)


def _bool_or_none(v):
    return v is None or isinstance(v, bool)


def _int_or_none(v):
    return v is None or _is_int(v)


def _items_fault(v, item_fault):
    """Where a list's item is malformed, as a path suffix (`[2].grade`), "" when `v` is no list, else None."""
    if not isinstance(v, list):
        return ""
    for j, x in enumerate(v):
        fault = item_fault(x)
        if fault is not None:
            return f"[{j}]{fault}"
    return None


def _range_fault(p):
    ok = isinstance(p, list) and len(p) == 2 and all(_is_int(x) for x in p) and 1 <= p[0] <= p[1]
    return None if ok else ""


def _part_fault(p):
    """Where one `{"file", "lines"}` entry is malformed, as a path suffix, else None."""
    if not isinstance(p, dict):
        return ""
    if not _nb(p.get("file")):
        return ".file"
    fault = _items_fault(p.get("lines"), _range_fault)
    return None if fault is None else f".lines{fault}"


def _run_fault(run):
    """Where one command run is malformed, as a path suffix, else None: a status, an exit code (an int when it
    ran, else null), the output and a reason."""
    if not isinstance(run, dict):
        return ""
    if run.get("status") not in RUN_STATUSES:
        return ".status"
    if not (_is_int(run.get("exitCode")) if run["status"] == "ran" else run.get("exitCode") is None):
        return ".exitCode"
    if not isinstance(run.get("output"), str):
        return ".output"
    return None if _str_or_none(run.get("reason")) else ".reason"


def _rerun_fault(c):
    if not isinstance(c, dict):
        return ""
    if not (_is_int(c.get("round")) and c["round"] >= 1):
        return ".round"
    if not _nb(c.get("check")):
        return ".check"
    if not (isinstance(c.get("runs"), list) and len(c["runs"]) == 2):
        return ".runs (needs exactly two)"
    fault = _items_fault(c["runs"], _run_fault)
    return None if fault is None else f".runs{fault}"


def _break_it_fault(x):
    if not isinstance(x, dict):
        return ""
    if not _nb(x.get("test")):
        return ".test"
    if not _nb_or_none(x.get("commit")):
        return ".commit"
    if not _nb_or_none(x.get("changedWhy")):
        return ".changedWhy"
    return _run_fault(x)


def _hit_fault(h):
    if not isinstance(h, dict):
        return ""
    for k in ("id", "file", "title"):
        if not _nb(h.get(k)):
            return f".{k}"
    return None if _int_or_none(h.get("line")) else ".line"


def _outside_fault(x):
    if not isinstance(x, dict):
        return ""
    src = x.get("source")
    if not isinstance(src, dict):
        return ".source"
    if src.get("kind") not in SOURCE_KINDS:
        return ".source.kind"
    if not _nb(src.get("name")):
        return ".source.name"
    if not (_nb(src.get("sweepId")) if src["kind"] == "sweep" else src.get("sweepId") is None):
        return ".source.sweepId"
    if not (isinstance(x.get("hits"), list) and x["hits"]):
        return ".hits"
    fault = _items_fault(x["hits"], _hit_fault)
    return None if fault is None else f".hits{fault}"


def _unread_fault(u):
    if not isinstance(u, dict):
        return ""
    for k in ("unreadLines", "countableLines"):
        if not (_is_int(u.get(k)) and u[k] >= 0):
            return f".{k}"
    if u["unreadLines"] > u["countableLines"]:
        return ".unreadLines (more than countableLines)"
    fault = _items_fault(u.get("parts"), _part_fault)
    return None if fault is None else f".parts{fault}"


def _grade_fault(g):
    if not isinstance(g, dict):
        return ""
    if g.get("verdict") not in GRADE_VERDICTS:
        return ".verdict"
    return None if _nb(g.get("reason")) else ".reason"


def _repeat_fault(g):
    if not isinstance(g, dict):
        return ""
    # axis: a repeat names the earlier finding by its stored key, never by an id alone — see bite-proof record c1l1_wo_a_record_seam
    if not _nb(g.get("findingKey")):
        return ".findingKey"
    if not _nb_or_none(g.get("id")):
        return ".id"
    return None if _bool_or_none(g.get("fixHolds")) else ".fixHolds"


def _place_fault(p):
    if not isinstance(p, dict):
        return ""
    if not _nb(p.get("file")):
        return ".file"
    if not _int_or_none(p.get("line")):
        return ".line"
    return None if _bool_or_none(p.get("fixed")) else ".fixed"


def _kind_fault(k):
    if not isinstance(k, dict):
        return ""
    if not _nb(k.get("kind")):
        return ".kind"
    fault = _items_fault(k.get("places"), _place_fault)
    return None if fault is None else f".places{fault}"


def _validate(a):
    def chk(ok, key):
        if not ok:
            raise Refusal("review-account-invalid", key)
    ne = lambda v: isinstance(v, str) and bool(v)  # noqa: E731
    sn = lambda v: v is None or isinstance(v, str)  # noqa: E731
    lst = lambda k: a.get(k, []) if isinstance(a.get(k, []), list) else chk(False, k)  # noqa: E731
    chk(isinstance(a, dict), "account")
    chk("findings" in a, "findings")  # an omitted findings member is unknown coverage, never an empty review
    chk(a.get("schema") == ACCOUNT_SCHEMA, "schema")
    pr = a.get("pr")
    chk(isinstance(pr, int) and not isinstance(pr, bool) and pr > 0, "pr")
    chk(a.get("repo") is None or (isinstance(a["repo"], str) and _REPO_RE.fullmatch(a["repo"])), "repo")
    chk(ne(a.get("sessionId")), "sessionId")
    for k in ("lane", "laneReason", "finalCommit", "ci"):
        chk(sn(a.get(k)), k)
    ab = a.get("abandoned")
    chk(ab is None or (isinstance(ab, dict) and isinstance(ab.get("reason"), str) and bool(ab["reason"].strip())), "abandoned")
    # an abandoned session may have run no seat, so only its record may list no reviewer
    chk(isinstance(a.get("reviewers"), list) and (a["reviewers"] or ab is not None), "reviewers")
    for i, r in enumerate(a["reviewers"]):
        chk(isinstance(r, dict), f"reviewers[{i}]")
        for k in ("name", "vendor", "model"):
            chk(ne(r.get(k)), f"reviewers[{i}].{k}")
        for k in ("planned", "ran"):
            chk(isinstance(r.get(k), bool), f"reviewers[{i}].{k}")
        chk(sn(r.get("runDir")), f"reviewers[{i}].runDir")
        chk(sn(r.get("commit")), f"reviewers[{i}].commit")
        chk(_step_ok(r.get("step")), f"reviewers[{i}].step")
        chk(r.get("notIndependent") is None or isinstance(r["notIndependent"], bool), f"reviewers[{i}].notIndependent")
        chk(r.get("ownerWord") is None or isinstance(r["ownerWord"], dict), f"reviewers[{i}].ownerWord")
        if "readParts" in r:
            fault = _items_fault(r["readParts"], _part_fault)
            # axis: a read-parts list is files with line ranges, never another shape — see bite-proof record c1l1_wo_a_record_seam
            chk(fault is None, f"reviewers[{i}].readParts{fault}")
        why = r.get("notRunReason")
        # axis: the not-run token labels only its own seat, never run, never attempted — see bite-proof record wo_1_1976_not_run_seat
        chk(why is None or (isinstance(why, str) and why in NOT_RUN_REASONS and r["name"] == NOT_RUN_REASONS[why][0]
                            and r["planned"] is True and r["ran"] is False and not r.get("runDir")
                            and r.get("commit") is None), f"reviewers[{i}].notRunReason")
    makers = a.get("makers")
    chk(makers is None or isinstance(makers, list), "makers")
    for i, m in enumerate(makers or []):
        chk(isinstance(m, dict) and ne(m.get("family")), f"makers[{i}]")
        chk(_step_ok(m.get("fromStep")), f"makers[{i}].fromStep")
    for i, f in enumerate(lst("findings")):
        chk(isinstance(f, dict) and ne(f.get("id")), f"findings[{i}].id")
        chk(f.get("outcome") is None or f["outcome"] in rfs.OUTCOMES,
            f"findings[{i}].outcome (allowed: {', '.join(rfs.OUTCOMES)}; or null while undecided)")
        chk(ne(f.get(session_contract.FINDING_KEY_FIELD)) or (ne(f.get("file")) and ne(f.get("title"))),
            f"findings[{i}] identity (needs findingKey, or file and title)")
        chk(sn(f.get("reason")), f"findings[{i}].reason")
        decided_by = session_contract.decided_by_of(f)
        chk(decided_by is None or isinstance(decided_by, dict), f"findings[{i}].decidedBy")
        chk(sn(f.get(rfs.CONSEQUENCE_KEY)), f"findings[{i}].{rfs.CONSEQUENCE_KEY}")
        if "grade" in f:
            fault = _grade_fault(f["grade"])
            # axis: a grade is a verdict from the vocabulary with a reason, never a bare mark — see bite-proof record c1l1_wo_a_record_seam
            chk(fault is None, f"findings[{i}].grade{fault}")
        if "repeatOf" in f:
            fault = _repeat_fault(f["repeatOf"])
            chk(fault is None, f"findings[{i}].repeatOf{fault}")
        if "breakItRuns" in f:
            fault = _items_fault(f["breakItRuns"], _break_it_fault)
            # axis: a break-it run says what ran, and carries an exit code exactly when it ran — see bite-proof record c1l1_wo_a_record_seam
            chk(fault is None, f"findings[{i}].breakItRuns{fault}")
        if "kindOfMistake" in f:
            fault = _kind_fault(f["kindOfMistake"])
            # axis: a kind of mistake names its kind and each place it recurs, never an unnamed place — see bite-proof record c1l1_wo_a_record_seam
            chk(fault is None, f"findings[{i}].kindOfMistake{fault}")
    for k in ("rawFindingsFiles", "checked"):
        chk(all(ne(x) for x in lst(k)), k)
    for i, g in enumerate(lst("goAheads")):
        chk(isinstance(g, dict) and ne(g.get("reviewer")) and g.get("kind") in ("standing-ruling", "owner-words"),
            f"goAheads[{i}]")
    for i, x in enumerate(lst("refused")):
        chk(isinstance(x, dict) and ne(x.get("title")) and ne(x.get("reason")), f"refused[{i}] (needs title and reason)")
    for i, x in enumerate(lst("commandRefusals")):
        where = f"commandRefusals[{i}]"
        chk(isinstance(x, dict), where)
        # axis: an entry is a valid refusal tagged with a real round, never a blank or foreign shape — see bite-proof record wo3_2011_record
        chk(isinstance(x.get("round"), int) and not isinstance(x["round"], bool) and x["round"] >= 1, f"{where}.round")
        fault = command_refusals.refusals_fault([{k: v for k, v in x.items() if k != "round"}])
        chk(fault is None, f"{where} ({fault})")
    named = []
    for i, c in enumerate(lst("carriedChecks")):
        where = f"carriedChecks[{i}]"
        chk(isinstance(c, dict) and ne(c.get("key")), f"{where}.key")
        chk(c.get("settled") in CARRIED_SETTLED, f"{where}.settled (allowed: {', '.join(CARRIED_SETTLED)})")
        chk(isinstance(c.get("evidence"), str) and bool(c["evidence"].strip()), f"{where}.evidence")
        for k in ("commit", "checkedHead"):
            chk(ne(c.get(k)) or (c.get(k) is None and c["settled"] != CARRIED_SETTLED[0]), f"{where}.{k}")
        hit = {j for j, f in enumerate(a["findings"]) if c["key"] in (_key(f), f["id"])}
        chk(len(hit) == 1, f"{where}.key names {'no finding' if not hit else 'more than one finding'}")
        chk(hit.isdisjoint(named), f"{where}.key names a finding another entry names")
        named += hit
    ruled = []
    for i, r in enumerate(lst("ownerRulings")):
        where = f"ownerRulings[{i}]"
        chk(isinstance(r, dict), where)
        for k in ("key", "url", "words"):
            chk(ne(r.get(k)) and r[k].strip() != "", f"{where}.{k}")
        hit = _ruling_hits(a["findings"], r["key"])
        # axis: an entry must name exactly one finding, and no finding is named twice — see bite-proof record wo_a_1958_owner_ruling
        chk(len(hit) == 1, f"{where}.key names {'no finding' if not hit else 'more than one finding'}")
        chk(hit.isdisjoint(ruled), f"{where}.key names a finding another entry names")
        ruled += hit
    chk(a.get("sheetAnswers") is None or isinstance(a["sheetAnswers"], dict), "sheetAnswers")
    chk(a.get("baseRef") is None or ne(a["baseRef"]), "baseRef")
    rounds = a.get("rounds", {"count": 0, "cap": None, "stoppedAtCap": False})
    chk(isinstance(rounds, dict) and isinstance(rounds.get("count"), int)
        and (rounds.get("cap") is None or isinstance(rounds["cap"], int))
        and isinstance(rounds.get("stoppedAtCap"), bool)
        and rounds.get("capKind", CAP_KINDS[0]) in CAP_KINDS
        and ("wider" not in rounds or _wider_ok(rounds["wider"])), "rounds")
    if "extraAudit" in rounds:
        extra = rounds["extraAudit"]
        # axis: the extra audit round is said with a reason and nothing else — see bite-proof record c1l1_wo_a_record_seam
        chk(isinstance(extra, dict) and set(extra) == {"why"} and _nb(extra["why"]), "rounds.extraAudit")
    if "rerunChecks" in a:
        fault = _items_fault(a["rerunChecks"], _rerun_fault)
        # axis: a re-run check holds the first failure and the one re-run, two runs, each with a coherent status — see bite-proof record c1l1_wo_a_record_seam
        chk(fault is None, f"rerunChecks{fault}")
    if "synthesisRounds" in a:
        sr = a["synthesisRounds"]
        # axis: the synthesis rounds are distinct rounds in ascending order — see bite-proof record c1l1_wo_a_record_seam
        chk(isinstance(sr, list) and all(_is_int(n) and n >= 1 for n in sr)
            and all(x < y for x, y in zip(sr, sr[1:])), "synthesisRounds")
    if "outsideThisPR" in a:
        fault = _items_fault(a["outsideThisPR"], _outside_fault)
        # axis: an outside entry names its source, a sweep id exactly for a sweep, and at least one hit — see bite-proof record c1l1_wo_a_record_seam
        chk(fault is None, f"outsideThisPR{fault}")
    if "unreadShare" in a:
        fault = _unread_fault(a["unreadShare"])
        # axis: the unread lines are part of the countable lines, and every range is a real span — see bite-proof record c1l1_wo_a_record_seam
        chk(fault is None, f"unreadShare{fault}")
    return {"repo": None, "lane": None, "laneReason": None, "finalCommit": None, "ci": None,
            "findings": [], "rawFindingsFiles": [], "goAheads": [], "checked": [], "makers": [], "refused": [],
            "commandRefusals": [], "carriedChecks": [], "ownerRulings": [], "sheetAnswers": None, "baseRef": None, **a,
            "makers": makers or [], "rounds": dict(rounds, capKind=rounds.get("capKind", CAP_KINDS[0]))}


# --- code facts ---

def _effective_runs(rows):
    """One workflow run per (workflow, event): the newest. A workflow that re-runs on the same commit
    leaves its older runs listed; only the newest one is current."""
    newest = {}
    for row in rows:
        key = (row.get("workflow_id") or row.get("name"), row.get("event"))
        rank = (row.get("run_number") or 0, row.get("id") or 0)
        if key not in newest or rank > newest[key][0]:
            newest[key] = (rank, row)
    return [row for _, row in newest.values()]


def _latest_checks(rows, workflow_rows):
    """One check run per check: the newest. A check is the same (name, app, workflow, event, head branch, pull
    request); a workflow that re-runs on the same commit leaves its older check runs listed, while two PRs
    sharing one head SHA stay apart by their branch and by their pull request numbers. A row whose check cannot be identified (no name, no id, no app, or a GitHub
    Actions run whose suite maps to no workflow run) is never reduced."""
    suites = {wr.get("check_suite_id"): (wr.get("workflow_id") or wr.get("name"), wr.get("event"),
                                         wr.get("head_branch"),
                                         tuple(sorted(pr.get("number") for pr in (wr.get("pull_requests") or [])
                                                      if isinstance(pr, dict))))
              for wr in workflow_rows if wr.get("check_suite_id") is not None}
    newest, passed = {}, []
    for row in rows:
        app = row.get("app") or {}
        suite = (row.get("check_suite") or {}).get("id")
        if not row.get("name") or row.get("id") is None or app.get("id") is None \
                or (app.get("slug") == "github-actions" and suite not in suites):
            passed.append(row)
            continue
        key = (row["name"], app["id"]) + suites.get(suite, (None, None, None, ()))
        if key not in newest or row["id"] > newest[key]["id"]:
            newest[key] = row
    return list(newest.values()) + passed


def _run_words(rows):
    return [f"run {r.get('id')} {r.get('conclusion') or r.get('status')}"
            for r in sorted(rows, key=lambda r: r.get("id") or 0)]


def ci_reading(check_runs, status, workflow_runs=None, declaration=("absent", None)):
    """CI's state with the declared workflow it was read from and one line saying how: green only when
    the project's CI ran and passed on the head. ``workflow_runs`` is ``{"workflow_runs": [row, ...]}``."""
    runs = _latest_checks((check_runs or {}).get("check_runs") or [], (workflow_runs or {}).get("workflow_runs") or [])
    status = status or {}
    effective = _effective_runs((workflow_runs or {}).get("workflow_runs") or [])
    kind, name = declaration
    declared = name if kind == "declared" else None
    # A status with total_count 0 reports "pending" while nothing is pending: no statuses at all.
    states = ([status.get("state")] + [s.get("state") for s in status.get("statuses") or []]
              if (status.get("total_count") or 0) > 0 else [])
    selected = [r for r in effective if r.get("name") == declared] if declared is not None else []
    if kind not in ("declared", "absent"):
        read = "the CI workflow declaration could not be read"
    elif declared is not None:
        read = (f"workflow {declared}: " + ", ".join(_run_words(selected))) if selected \
            else f"workflow {declared}: no run on this commit"
    elif effective:
        read = "no CI workflow declared; GitHub Actions runs: " + ", ".join(
            f"{r.get('name')} {_run_words([r])[0]}" for r in sorted(effective, key=lambda r: r.get("id") or 0))
    else:
        read = "no CI workflow declared; no GitHub Actions run on this commit"

    def reading(state):
        return {"state": state, "workflow": declared, "read": read}

    if any(r.get("conclusion") in _RED for r in runs) or any(s in ("failure", "error") for s in states) \
            or any(r.get("status") == "completed" and r.get("conclusion") in _RED for r in effective):
        return reading("red")
    if kind not in ("declared", "absent"):
        return reading("none")
    if declared is not None:
        if not selected:
            return reading("none")
        if any(r.get("status") != "completed" for r in selected):
            return reading("pending")
        return reading("green" if any(r.get("conclusion") == "success" for r in selected) else "none")
    if any(r.get("status") != "completed" for r in effective):
        return reading("pending")
    if not runs and not states:
        return reading("none")
    if any(r.get("status") != "completed" for r in runs) or "pending" in states:
        return reading("pending")
    # with no declaration, green also needs an effective GitHub Actions run that concluded success
    ran_ok = any(r.get("status") == "completed" and r.get("conclusion") == "success" for r in effective)
    return reading("green" if ran_ok else "none")


def ci_state(check_runs, status, workflow_runs=None, declaration=("absent", None)):
    return ci_reading(check_runs, status, workflow_runs, declaration)["state"]


def _ci(rd, repo, sha, repo_root):
    declaration = rd["ci_workflow"](repo_root)
    data = rd["check_data"](sha, repo) if sha else None
    if data is None:
        return {"state": "none", "sha": None, "source": "unavailable",
                "workflow": declaration[1] if declaration[0] == "declared" else None, "read": "CI could not be read"}
    r = ci_reading(*data, declaration)
    return {"state": r["state"], "sha": sha, "source": "GitHub checks", "workflow": r["workflow"], "read": r["read"]}


def _lane_call(a, rd, meta):
    """The first lane-call line in the PR's closing issues' bodies, then the PR body, as (match, source)."""
    if meta:
        texts = [(rd["issue_body"](n, a["repo"]), "issue lane call") for n in meta["issues"]]
        for body, source in texts + [(meta["body"], "PR lane call")]:
            hit = _LANE_RE.search(body or "")
            if hit:
                return hit, source
    return None, None


def _lane_reason(text):
    """A lane call's reason without the punctuation that joined it to the lane word; None when nothing is left."""
    # axis: leading punctuation is not part of a reason, so the line never reads "because , ..." — see bite-proof record c7l3_wo1_record_writer
    return _REASON_LEAD_RE.sub("", text or "").strip() or None


def _lane(a, rd, meta):
    m = rd["lane_marker"](a.get("repoRoot"))
    hit, source = _lane_call(a, rd, meta)
    if isinstance(m, dict) and m.get("schema") == build_lane.BUILD_LANE_SCHEMA and m.get("lane") == "full" \
            and m.get("branch") == m.get("currentBranch") and meta \
            and str(m.get("issue")) in {str(n) for n in meta["issues"]}:
        # The marker decides the value only; a reason is shown with where it came from, never as a fact code holds.
        if hit and _lane_reason(hit.group(2)):
            reason, reason_source = _lane_reason(hit.group(2)), source
        elif a["laneReason"]:
            reason, reason_source = a["laneReason"], SESSION
        else:
            reason, reason_source = None, None
        return {"value": "full", "source": "build lane marker", "reason": reason, "reasonSource": reason_source}
    if hit:
        return {"value": hit.group(1), "source": source, "reason": _lane_reason(hit.group(2))}
    return {"value": a["lane"], "source": SESSION, "reason": a["laneReason"]}


BASIS_EVIDENCE_MAX = 10      # matched or unmatchable paths kept per list
BASIS_AREAS_MAX = 20         # touched areas kept on the record
BASIS_PATHS_MAX = 40         # matched paths kept across all touched areas together
BASIS_WHY_MAX = 12           # reason lines kept; the touches ones are the cut ones
BASIS_TEXT_MAX = 300         # characters kept of any one path, area name or reason line


def _clip(text):
    text = str(text)
    return text if len(text) <= BASIS_TEXT_MAX else text[:BASIS_TEXT_MAX - 1] + "\u2026"


def _bound_basis(basis):
    """The basis as it goes on the record, bounded in total: at most BASIS_AREAS_MAX touched areas,
    BASIS_PATHS_MAX matched paths across all of them (BASIS_EVIDENCE_MAX each), BASIS_EVIDENCE_MAX unmatchable
    paths, BASIS_WHY_MAX reason lines, and BASIS_TEXT_MAX characters of any one string. The counts of
    everything cut sit beside it (matchedCount, touchedCount, unmatchableCount, whyCount). The floor, the
    first reason and the lane-defining reasons are unchanged."""
    cap, budget, touched = BASIS_EVIDENCE_MAX, BASIS_PATHS_MAX, []
    for hit in basis["touched"][:BASIS_AREAS_MAX]:
        keep = max(0, min(cap, budget, len(hit["matched"])))
        budget -= keep
        item = dict(hit, name=_clip(hit["name"]), matched=[_clip(m) for m in hit["matched"][:keep]])
        if keep < len(hit["matched"]):
            item["matchedCount"] = len(hit["matched"])
        touched.append(item)
    out = dict(basis, touched=touched)
    if len(basis["touched"]) > BASIS_AREAS_MAX:
        out["touchedCount"] = len(basis["touched"])
        out["matchedTotal"] = sum(len(t["matched"]) for t in basis["touched"])
    if len(basis["unmatchable"]) > cap:
        out.update(unmatchable=[_clip(u) for u in basis["unmatchable"][:cap]],
                   unmatchableCount=len(basis["unmatchable"]))
    else:
        out["unmatchable"] = [_clip(u) for u in basis["unmatchable"]]
    why = list(basis["why"])
    if len(why) > BASIS_WHY_MAX:
        # Drop only the touches lines, from the end, so the verdict lines stay; say how many went.
        drop = len(why) - BASIS_WHY_MAX + 1
        idx = [i for i, w in enumerate(why) if i and lane_call.is_touches_line(w)][::-1][:drop]
        if idx:
            gone = set(sorted(idx)[-drop:])
            at = min(gone)
            why = [w for i, w in enumerate(why) if i not in gone]
            why.insert(at, lane_call.touches_omitted_line(len(gone)))
            out["whyCount"] = len(basis["why"])
    out["why"] = [_clip(w) for w in why]
    return out


def _lane_basis(a, rd, lane_value, final_sha):
    """The risk floor for the PR's changed files, from lane_call.call, with the record's own lane as the
    proposal. An account that names no repository, files that cannot be read, or a PR head that moved
    from the recorded final commit while they were read, give the floor full,
    marked unavailable, never a basis from the ambient project or from a partial list."""
    repo_root = a.get("repoRoot")
    # axis: an account that names no repository reads nothing, so no other project's store is read — see bite-proof record wo_c_1795_lane-basis
    if not repo_root:
        return dict(lane_call.unavailable(
            lane_call.WHY_NOT_SET + " the account names no repository, so its risk areas were not read",
            proposed=lane_value), source="unavailable")
    paths = rd["changed_paths"](a["pr"], a["repo"])
    # axis: a file list read after the PR head moved is not the recorded commit's change, so it is unavailable, never evaluated against that commit — see bite-proof record wo_a_1795_lane-call
    after = rd["pr_meta"](a["pr"], a["repo"])
    head = after.get("head") if isinstance(after, dict) else None
    moved = isinstance(head, str) and head != final_sha
    if isinstance(paths, list) and not head:
        return dict(lane_call.unavailable(
            lane_call.WHY_NO_PATHS + " the PR head could not be re-read while its changed files were read",
            proposed=lane_value), source="unavailable")
    if isinstance(paths, list) and moved:
        return dict(lane_call.unavailable(
            lane_call.WHY_NO_PATHS + " the PR head moved while its changed files were read",
            proposed=lane_value), source="unavailable", headMoved=True)
    if isinstance(paths, list):
        return dict(_bound_basis(lane_call.call(repo_root, paths, proposed=lane_value)),
                    source="lane rule over the PR's changed files")
    out = dict(lane_call.unavailable(
        lane_call.WHY_NO_PATHS + " the PR's changed files could not be read", proposed=lane_value),
        source="unavailable")
    if moved:
        out["headMoved"] = True
    return out


def _canonical_model(vendor, model):
    """A model as the registry's id: a dispatch spelling (a Claude tier alias, a Cursor id with its effort
    suffix) resolves to the id the engine record carries; an unrecognised string stays as written."""
    if not isinstance(vendor, str) or not isinstance(model, str) or model_registry.is_registered(vendor, model):
        return model
    parsed = model_registry.parse_dispatch_token(vendor, model)
    return parsed[0] if parsed else model


def _family(vendor, model):
    fam = model_registry.model_family(vendor, model)
    if fam or vendor not in _VENDOR_MODELS:
        return fam
    shared = {model_registry.model_family(vendor, m) for m in _VENDOR_MODELS[vendor]()}
    return shared.pop() if len(shared) == 1 else None


def _go_ahead_ok(g):
    need = ("canonId",) if g.get("kind") == "standing-ruling" else ("words", "where")
    return all(isinstance(g.get(k), str) and g[k].strip() for k in need)


def _go_text(g):
    return f"standing ruling {g['canonId']}" if g["kind"] == "standing-ruling" else f"owner's words ({g['where']})"


def _short(sha):
    return (sha or "")[:7] or "unknown"


def _own_word_ok(word):
    return isinstance(word, dict) and all(isinstance(word.get(k), str) and word[k].strip() for k in ("words", "where"))


def _reviewer(r, rd, dis, head, shared=frozenset(), reported_commit=None, lane_value=None, maker_families=frozenset()):
    out = {k: r.get(k) for k in ("name", "vendor", "model", "planned", "runDir")}
    out["family"] = _family(r["vendor"], r["model"])
    if "readParts" in r:
        out["readParts"] = r["readParts"]
    # The runner's record does not expose a findings run's content: the code holds no reviewer's findings.
    out["findingsCoverage"] = SESSION
    named = isinstance(r.get("commit"), str) and bool(r["commit"])
    target = r["commit"] if named else head
    credited = None
    if r.get("runDir") and os.path.realpath(r["runDir"]) in shared:
        out.update(ran="not-run", runNote="the run record is claimed by more than one reviewer")
        if r["ran"]:
            dis.append({"fact": f"{r['name']} ran", "session": True, "code": "not-run"})
    elif r.get("runDir"):
        rec, err = rd["engine_run"](r["runDir"])
        seen = rec.get("viewHeadSha") if isinstance(rec, dict) else None
        graded = isinstance(rec, dict) and rec.get("graded") is True
        review = isinstance(rec, dict) and rec.get("runKind") == session_contract.RUN_KIND_REVIEW
        # A run is credited against exactly one commit: the one the row names, else the final commit.
        where = f"the commit this reviewer was listed for {_short(target)}" if named else "the final commit"
        if isinstance(seen, str) and seen and seen == target and graded and review:
            out.update(ran="engine-record", observation=rec.get("observation"))
            credited = rec
        else:
            if not isinstance(rec, dict):
                note = err if isinstance(err, str) and err else "no run record"
            elif isinstance(seen, str) and seen and seen != target:
                note = f"the run record covers {_short(seen)}, not " + (where if named else f"{where} {_short(head)}")
            elif isinstance(seen, str) and seen and not review:
                note = f"the run on {where} was not a completed review run"
            elif isinstance(seen, str) and seen:
                note = f"the run on {where} did not complete a review (forfeit or failure)"
            else:
                note = "the run record names no commit"
            out.update(ran="not-run", runNote=note)
            if r["ran"]:
                dis.append({"fact": f"{r['name']} ran", "session": True, "code": "not-run"})
    elif r["ran"] and (named or (reported_commit and reported_commit == head)):
        out["ran"] = "reported-by-session"
    elif r["ran"]:
        note = (f"the session reported a review of {_short(reported_commit)}, not the final commit {_short(head)}"
                if reported_commit else "the session did not say which commit it reviewed")
        out.update(ran="not-run", runNote=note)
        dis.append({"fact": f"{r['name']} ran", "session": True, "code": "not-run"})
    else:
        out["ran"] = "not-run"

    def demote(note):
        out.pop("observation", None)
        out.update(ran="not-run", runNote=note)
        if r["ran"]:
            dis.append({"fact": f"{r['name']} ran", "session": True, "code": "not-run"})

    # axis: the credited run is the run the row names; the family is read from the engine record, never from the row — see bite-proof record wo_a_1796_reading-independence
    if credited is not None:
        if credited.get("source") != r["vendor"] \
                or _canonical_model(r["vendor"], credited.get("engineModel")) != _canonical_model(r["vendor"], r["model"]):
            demote("the run record names a different reviewer than the account row")
        else:
            out["family"] = _family(credited["source"], credited["engineModel"])
    if lane_value != "full":
        # axis: outside the full lane a reviewer counts only when the engine's own record reads engaged — see bite-proof record wo_a_1796_reading-independence
        if out["ran"] == "engine-record":
            obs = out.get("observation")
            if not isinstance(obs, dict) or obs.get("read") != "engaged":
                demote("the engine's record of the run does not show that the reviewer read the change")
        elif out["ran"] == "reported-by-session":
            demote("no engine record of the run shows that the reviewer read the change")
        out["reading"] = "engaged" if out["ran"] == "engine-record" else "not-shown"
    # axis: a reviewer from a maker's family counts only with the owner's word; independence is computed here, never taken from the account — see bite-proof record wo_a_1796_reading-independence
    if out["ran"] != "not-run" and maker_families is None:
        demote("no maker is named for the step this reviewer reviewed, so independence cannot be shown")
    elif out["ran"] != "not-run" and maker_families:
        if out["family"] is None:
            demote("the reviewer's model family could not be read, so independence cannot be shown")
        elif out["family"] in maker_families:
            if _own_word_ok(r.get("ownerWord")):
                out["notIndependent"] = True
            else:
                demote("the reviewer is from a maker's family and no owner's word for this change lets it run")
    out["commit"] = target if named else None
    out["coversFinalCommit"] = bool(head) and out["ran"] != "not-run" and target == head
    if isinstance(r.get("ownerWord"), dict):
        out["ownerWord"] = r["ownerWord"]
    # axis: a row's cost is read from the engine record that credited it, never from the account; unmeasured is null, never zero — see bite-proof record c1l1_wo_a_record_seam
    obs = out.get("observation") if out["ran"] == RAN_ENGINE_RECORD else None
    obs = obs if isinstance(obs, dict) else {}
    wall = obs.get("wallSeconds")
    out["cost"] = {"tokens": obs.get("tokens") if _is_int(obs.get("tokens")) else None,
                   "minutes": round(wall / 60, 1) if isinstance(wall, (int, float)) and not isinstance(wall, bool) else None}
    return out


_OPAQUE_KEY = "rr1:"


def _key(f):
    """A finding's stable opaque identity, derived from the unredacted account.

    A hash, so redaction can neither change it nor expose text carried in the identity.
    """
    raw = session_contract.finding_identity_key(f)
    if not isinstance(raw, str) or raw.startswith(_OPAQUE_KEY):
        return raw
    return _OPAQUE_KEY + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]


def _name(f):
    return f.get("id") or f"at {f.get('file')}:{f.get('line')}"


def _unaccounted(prior, findings):
    """The only reader of an earlier record: the names of its findings this account does not list.

    Compared by stored identity key (session_contract.finding_identity_key), never by id. A malformed
    findings list is never read as an empty one.
    """
    if prior is None:
        return []
    earlier = prior.get("findings")
    if not isinstance(earlier, list) or not all(isinstance(i, dict) for i in earlier):
        raise Refusal("review-record-unreadable", "the latest record's findings list is malformed")
    present = {_key(f) for f in findings}
    return [i.get("id") or _key(i) for i in earlier if _key(i) not in present]


def leftover_line(finding):
    """The one home of the leftover's whatIsMissing wording; the sheet reads it."""
    return f"finding {_name(finding)} waits for the owner's decision"


REVIEWED = "reviewed"
NOT_REVIEWED = "not-reviewed"
AWAITS_OWNER = "awaits-owner"
STATUSES = (REVIEWED, NOT_REVIEWED, AWAITS_OWNER)


def cleared(status):
    """Only `reviewed` clears a gate; any other value, an unknown one included, does not."""
    return status == REVIEWED


def _finding_lines(findings):
    lines = []
    for f in findings:
        if f.get("outcome") not in rfs.OUTCOMES:
            lines.append(f"finding {_name(f)} has no outcome")
        elif not f.get("reason"):
            lines.append(f"finding {_name(f)} has no reason")
        elif f["outcome"] == _LEFT_FOR_OWNER:
            lines.append(leftover_line(f))
    return lines


def _lane_lines(rec):
    lane, basis = rec["lane"]["value"], rec["laneBasis"]
    # axis: a lane below the risk floor is not-reviewed; an unknown lane counts as below — see bite-proof record wo_a_1795_lane-call
    if basis["floor"] is not None and lane_call.rank(lane) < lane_call.rank(basis["floor"]):
        # fixed prose: only the lane and floor tokens enter, never the basis's free-text reasons (the Risk floor line holds those)
        lines = [f"the lane ({lane}) is below the risk floor ({basis['floor']}); the Risk floor line gives why"]
    else:
        lines = []
    # axis: a head read and found moved from the recorded final commit is not-reviewed, whatever the lane — see bite-proof record wo_g_1795_head-moved
    if basis.get("headMoved"):
        # fixed prose: no data enters
        lines.append("the PR head moved while the record was written; this record does not cover the new head")
    return lines


def _status(rec, unread=(), finding_lines=()):
    fc, ci, lines = rec["finalCommit"], rec["ci"], list(unread)
    s7 = lambda sha: (sha or "")[:7] or "unknown"  # noqa: E731
    if fc["source"] != "GitHub PR":
        lines.append("the final commit could not be read from the PR")
    if ci["source"] == "unavailable":
        lines.append("CI could not be read")
    elif ci["state"] != "green":
        lines.append(f"CI is {ci['state']} on {s7(ci['sha'])}" + (f" ({ci['read']})" if ci.get("read") else ""))
    elif ci["sha"] != fc["sha"]:
        lines.append(f"CI was read on {s7(ci['sha'])}, not on the final commit {s7(fc['sha'])}")
    lines += finding_lines
    lines += _lane_lines(rec)
    # axis: no named maker is not-reviewed, since independence cannot be shown — see bite-proof record wo_a_1796_reading-independence
    if not rec["makers"]:
        # fixed prose: no data enters
        lines.append("no maker is named, so independence cannot be shown")
    lines += [f"the session ended on {s7(d['session'])}, but the PR's final commit is {s7(d['code'])}"
              for d in rec["sessionDisagreements"] if d["fact"] == "finalCommit"]
    for m in rec["missingReviews"]:
        lines.append(f"{m['name']} did not run" + (f"; go-ahead: {_go_text(m['goAhead'])}" if m["goAhead"] else ""))
    ran = [v for v in rec["reviewers"] if v["planned"] and v["ran"] != "not-run"]
    if not ran:
        lines.append("no planned reviewer ran")
    elif not any(v["coversFinalCommit"] for v in ran):
        lines.append(f"no planned reviewer's run covers the final commit {s7(fc['sha'])}")
    # axis: an abandoned session's record never reads reviewed — see bite-proof record wo_b_2137_abandoned_record
    if rec.get("abandoned"):
        # fixed prose: no data enters
        lines.append("session abandoned: the review loop was closed before it ended, so this record cannot read reviewed")
    return (NOT_REVIEWED if lines else REVIEWED), any(m["goAhead"] is None for m in rec["missingReviews"]), lines


def _owner_only(rec, missing_lines):
    """True when the record reads not-reviewed, is not parked, and every missing line is a leftover line: with its leftovers it reads awaits-owner exactly when the same record without them reads reviewed."""
    if rec["status"] != NOT_REVIEWED or rec["parked"]:
        return False
    leftovers = {leftover_line(f) for f in rec["findings"] if f.get("outcome") == _LEFT_FOR_OWNER}
    # axis: a record is awaits-owner only when every missing line is a leftover finding
    if not missing_lines or not all(m in leftovers for m in missing_lines):
        return False
    return True


def _ruling_hits(findings, key):
    """The indexes of the account findings an ownerRulings key names: by raw findingKey, stored identity key or id."""
    return {j for j, f in enumerate(findings)
            if key in (f.get(session_contract.FINDING_KEY_FIELD), _key(f), f["id"])}


def _apply_owner_rulings(findings, raw, entries):
    """Set the owner-ruling citation as decidedBy on each ruling or left-for-owner finding an entry names.
    `raw` is the account's findings as given (an entry may key by the raw findingKey the stamping replaced);
    `findings` is the same list after the stamping. Every other outcome is left exactly as it is."""
    out = list(findings)
    for e in entries:
        (j,) = _ruling_hits(raw, e["key"])
        if out[j].get("outcome") in (_RULING, _LEFT_FOR_OWNER):
            # axis: an entry sets the citation on the finding it names, and on no other outcome — see bite-proof record wo_a_1958_owner_ruling
            out[j] = dict(out[j], decidedBy={"kind": finding_outcomes.OWNER_RULING, "ref": {"url": e["url"], "words": e["words"]}})
    return out


def _recheck_decisions(findings, sources):
    """Check every cited decision against what is on record now. A ruling whose cited decision is not on record
    goes to the owner; a finding left for the owner whose cited decision is on record becomes the ruling. A ruling
    with no cited decision names its basis in prose, which the record cannot check, so it stays as it is. A
    ruling whose cited owner ruling resolves stays a ruling and its reason leads with the citation, once. A
    finding with no reason keeps none (its missing reason still counts against the record), except that one.
    Returns the findings and one entry per change."""
    out, changes = [], []
    for f in findings:
        by, outcome, reason = f.get("decidedBy"), f.get("outcome"), f.get("reason")
        new, unmet, refreshed = None, None, None
        if isinstance(by, dict) and outcome in (_RULING, _LEFT_FOR_OWNER):
            # axis: a ruling stands only while the decision it cites is on record now, checked at write time — see bite-proof record c7l3_wo1_record_writer
            ok, text = finding_outcomes.on_record(by, sources())
            if outcome == _RULING and not ok:
                new, why = _LEFT_FOR_OWNER, f"the cited decision is not on record ({text})"
            elif outcome == _LEFT_FOR_OWNER and ok:
                new, why = _RULING, text
            elif outcome == _RULING and ok and by.get("kind") == finding_outcomes.OWNER_RULING:
                refreshed = text
            elif outcome == _LEFT_FOR_OWNER and by.get("kind") == finding_outcomes.OWNER_RULING and not ok:
                # axis: a finding whose owner ruling does not resolve says so in its reason, and stays for the owner — see bite-proof record wo_a_1958_owner_ruling
                unmet = f"the owner ruling it cites is not on record ({text})"
        if new is None:
            if refreshed:
                # axis: an already-ruling finding whose owner-ruling citation resolves shows the citation as its reason, once, and keeps its outcome — see bite-proof record wo_a_1958_owner_ruling
                if not reason:
                    f = dict(f, reason=refreshed)
                elif isinstance(reason, str) and not reason.startswith(refreshed):
                    f = dict(f, reason=f"{refreshed}; {reason}")
                out.append(f)
                continue
            out.append(dict(f, reason=f"{reason}; {unmet}") if unmet and reason else f)
            continue
        out.append(dict(f, outcome=new, reason=f"{why}; {reason}" if reason else reason))
        changes.append({"finding": _name(f), "from": outcome, "to": new, "why": why})
    return out, changes


def _recheck_carried(findings, checks, prior, head, is_ancestor):
    """Re-check each left-for-owner finding a carried check names against the record's final commit `head`.
    A finding moves to fixed only on a `fixed` entry for a finding carried from `prior`, checked on `head`, whose
    fix commit is in `head`'s history (is_ancestor exactly True); every other case keeps its outcome, with the
    reason saying why. A finding is never removed. Returns the findings and one row per entry."""
    earlier = prior.get("findings") if isinstance(prior, dict) else None
    stored = {_key(i) for i in earlier if isinstance(i, dict)} if isinstance(earlier, list) else set()
    out, rows = [], []
    for f in findings:
        c = next((c for c in checks if c["key"] in (f.get(session_contract.FINDING_KEY_FIELD), f.get("id"))), None)
        if c is None:
            out.append(f)
            continue
        settled, commit, seen, evidence, old = c["settled"], c.get("commit"), c.get("checkedHead"), c["evidence"], f.get("reason")
        shown, result, why, moved = (head or "unknown")[:7], "kept", None, False
        if f.get("outcome") != _LEFT_FOR_OWNER:
            result, why = "unchanged", "not left for the owner"
        elif settled == "applies":
            why = f"the check found it still applies: {evidence}"
        elif settled == "unsettled":
            why = f"the check could not settle it: {evidence}"
        # axis: a finding is marked fixed only if it was carried from the earlier record — see bite-proof record wo_b_1933_carried-recheck
        elif _key(f) not in stored:
            why = "not carried from an earlier record"
        # axis: a check counts only for the commit the record names as final, so a head that moved after it keeps the finding — see bite-proof record wo_b_1933_carried-recheck
        elif seen != head:
            why, moved = f"checked on {seen[:7]}, not the final commit {shown}", True
        else:
            # axis: the fix commit counts as in the history only when the read returns exactly True; unknown keeps the finding — see bite-proof record wo_b_1933_carried-recheck
            in_history = is_ancestor(commit, head)
            if in_history is False:
                why = f"its fix commit {commit[:7]} is not in the final commit's history"
            elif in_history is not True:
                why = "its fix commit's place in the history could not be read"
        if why is None:
            result = "fixed"
            reason = (f"fixed after its review at {commit[:7]}: {evidence} "
                      f"(checked against the final commit {shown} when this record was written)")
            out.append(dict(f, outcome="fixed", reason=f"{reason}; earlier: {old}" if old else reason))
        elif result == "kept":
            # axis: a kept reason never claims the final commit unless the check ran on it
            on = ("a check on no named commit" if seen is None else "a check" if moved
                  else "a check against the final commit" if seen == head
                  else f"a check on {seen[:7]} (not the final commit {shown})")
            kept = f"{on} kept it for the owner: {why}"
            out.append(dict(f, reason=f"{old}; {kept}" if old else kept))
        else:
            out.append(f)
        rows.append({"finding": _name(f), "settled": settled, "result": result, "why": why or "fixed",
                     "commit": commit, "checkedHead": seen, "evidence": evidence})
    return out, rows


def build_record(account, readers, prior=None):
    a, rd, dis = _validate(account), _readers(readers), []
    read_paths, seen = rd["changed_paths"], {}

    def cached_paths(pr, repo):
        # The PR's changed files are read once per write, so the lane basis and the withheld list agree.
        if (pr, repo) not in seen:
            seen[(pr, repo)] = read_paths(pr, repo)
        return seen[(pr, repo)]

    rd = dict(rd, changed_paths=cached_paths)
    meta = rd["pr_meta"](a["pr"], a["repo"])
    fc = {"sha": meta["head"], "source": "GitHub PR"} if meta else {"sha": a["finalCommit"], "source": SESSION}
    ci, lane = _ci(rd, a["repo"], fc["sha"], a.get("repoRoot")), _lane(a, rd, meta)
    for fact, session, code, from_code in (("lane", a["lane"], lane["value"], lane["source"] != SESSION),
                                           ("finalCommit", a["finalCommit"], fc["sha"], bool(meta)),
                                           ("ci", a["ci"], ci["state"], ci["source"] == "GitHub checks")):
        if from_code and session is not None and session != code:
            dis.append({"fact": fact, "session": session, "code": code})
    dirs = [os.path.realpath(r["runDir"]) for r in a["reviewers"] if r.get("runDir")]
    shared = frozenset(d for d in dirs if dirs.count(d) > 1)
    reviewers = [_reviewer(r, rd, dis, fc["sha"], shared, a["finalCommit"], lane["value"],
                           _makers_for(a["makers"], r.get("step")) or (None if a["makers"] else frozenset()))
                 for r in a["reviewers"]]
    notes, missing, seats_not_run, held = [], [], [], {}
    # Identity is stamped on the unredacted account, so a later write compares the stored key.
    findings = [dict(f, **{session_contract.FINDING_KEY_FIELD: _key(f)}) for f in a["findings"]]
    findings = _apply_owner_rulings(findings, a["findings"], a["ownerRulings"])

    def owner_ruling_comments():
        # One read per distinct cited link, and none for a link that is not a comment permalink in this repository.
        docs = {}
        for f in findings:
            by, ref = f.get("decidedBy"), None
            if isinstance(by, dict) and by.get("kind") == finding_outcomes.OWNER_RULING and f.get("outcome") in (_RULING, _LEFT_FOR_OWNER):
                ref = by.get("ref")
            url = ref.get("url") if isinstance(ref, dict) else None
            parts = finding_outcomes.comment_permalink(url, a["repo"])[0] if isinstance(url, str) else None
            if parts is not None and url not in docs:
                try:
                    docs[url] = rd["owner_ruling_comment"](a["repo"], parts[3])
                except Exception:  # noqa: BLE001 — fail closed: a comment that cannot be read is not on record
                    docs[url] = None
        return docs

    def sources():
        # Read once, and only when a cited decision needs it: Canon and residuals as the repository holds them now.
        if "sources" not in held:
            try:
                base = rd["decision_sources"](a.get("repoRoot"), a.get("baseRef"), a.get("sheetAnswers"), a["pr"])
            except Exception:  # noqa: BLE001 — fail toward the owner: no sources means no cited decision is on record
                base = {}
            held["sources"] = dict(base if isinstance(base, dict) else {}, repo=a["repo"], ownerRulings=owner_ruling_comments())
        return held["sources"]

    def canon_on_record(g):
        return g.get("kind") != "standing-ruling" or finding_outcomes.on_record(
            {"kind": "canon", "ref": g["canonId"]}, sources())[0]

    for v, row in zip(reviewers, a["reviewers"]):  # built in the account's order
        if v["planned"] and v["ran"] == "not-run":
            token = row.get("notRunReason")
            if token:  # the writer checked it labels only its own seat, never run
                seats_not_run.append({"name": v["name"], "reason": token, "why": NOT_RUN_REASONS[token][1]})
                continue
            mine = [g for g in a["goAheads"] if g["reviewer"] == v["name"]]
            complete = [g for g in mine if _go_ahead_ok(g)]
            # axis: a standing-ruling go-ahead counts only while its Canon entry is on record — see bite-proof record c7l3_wo1_record_writer
            good = next((g for g in complete if canon_on_record(g)), None)
            if mine and not good:
                notes.append(f"the go-ahead for {v['name']} is incomplete"
                             + (" (its Canon entry is not on record)" if complete else ""))
            missing.append({"name": v["name"], "goAhead": good})
    unread = [str(p) for p in a["rawFindingsFiles"] if rd["read_text"](p) is None]
    findings, rechecks = _recheck_decisions(findings, sources)
    findings, carried_rows = _recheck_carried(findings, a["carriedChecks"], prior, fc["sha"],
                                              lambda commit, head: rd["is_ancestor"](a.get("repoRoot"), commit, head))
    findings = [dict(f, sheetPart=rfs.OUTCOME_SHEET_PART.get(f.get("outcome"))) for f in findings]
    walls = [v["observation"].get("wallSeconds") for v in reviewers if v["ran"] == "engine-record"
             and isinstance(v.get("observation"), dict)]
    toks = [v["observation"].get("tokens") for v in reviewers if v["ran"] == "engine-record"
            and isinstance(v.get("observation"), dict)]
    toks = [t for t in toks if isinstance(t, int) and not isinstance(t, bool)]
    ran_names = [v["name"] for v in reviewers if v["ran"] != "not-run"]
    # An account that names no repository reads no changed files, so the list is unknown.
    paths = rd["changed_paths"](a["pr"], a["repo"]) if a.get("repoRoot") else None
    withheld = rd["withheld_paths"](a.get("repoRoot"), fc["sha"], paths) if isinstance(paths, list) else None
    rec = {
        "schema": RECORD_SCHEMA, "pr": a["pr"], "sessionId": a["sessionId"], "lane": lane, "makers": a["makers"],
        "laneBasis": _lane_basis(a, rd, lane["value"], fc["sha"]), "finalCommit": fc,
        "withheldFromReviewers": withheld,
        **({"abandoned": a["abandoned"]} if a.get("abandoned") else {}),
        "ci": ci, "reviewers": reviewers, "findings": findings, "decisionRechecks": rechecks,
        "carriedRechecks": carried_rows,
        "refused": a["refused"], **({"commandRefusals": a["commandRefusals"]} if a["commandRefusals"] else {}),
        # axis: a part shows in the record exactly when the account carries it — see bite-proof record c1l1_wo_a_record_seam
        **{k: a[k] for k in _ROUND_PARTS if k in a},
        "unreadFiles": unread, "rawOutputs": [],
        "leftForOwner": [_name(f) for f in findings if f.get("outcome") == _LEFT_FOR_OWNER],
        "missingReviews": missing, **({"seatsNotRun": seats_not_run} if seats_not_run else {}),
        "rounds": dict({k: v for k, v in a["rounds"].items() if k != "wider" or v}, source=SESSION),
        "cost": {"unit": "reviewer-minutes",
                 "minutes": round(sum(w for w in walls if isinstance(w, (int, float))) / 60, 1),
                 "tokens": sum(toks) if toks else None, "source": "engine records",
                 "notCounted": [v["name"] for v in reviewers if v["ran"] != "engine-record"]},
        "sessionDisagreements": dis,
        "checked": [f"CI on {(fc['sha'] or 'unknown')[:7]}: {ci['state']}",
                    "Reviewers that ran: " + (", ".join(ran_names) or "none")] + a["checked"],
        "previousRecord": None,
        "earlierRecordsNotChecked": [],
        "writtenAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    rec["status"], rec["parked"], lines = _status(
        rec, [f"the raw output file {n} could not be read" for n in unread], _finding_lines(findings))
    rec["whatIsMissing"] = notes + lines
    if _owner_only(rec, rec["whatIsMissing"]):
        rec["status"] = AWAITS_OWNER
    return rec


# --- render, write, read ---

def _assert_no_bug_free_claim(text):
    low = text.lower()
    for phrase in FORBIDDEN_CLAIMS:
        if phrase in low:
            raise Refusal("review-record-forbidden-claim", phrase)


_SECRET_SUBSTRINGS = ("password", "passwd", "pwd", "passphrase", "secret", "token", "credential", "authorization",
                      "cookie", "apikey", "privatekey", "secretkey", "accesskey")
_KEY_QUOTES = "\"'`[]{}() \t\\"
_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")
_KEY_CANDIDATE = re.compile(r"(?<![A-Za-z0-9])(?P<key>[A-Za-z][A-Za-z0-9_.\-]{0,63}(?: [A-Za-z][A-Za-z0-9_.\-]{0,63})?)[^\w\n:=]*[:=]")
_PEM_BEGIN = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
_JSON_ESCAPE = re.compile(r'\\(?:u[0-9a-fA-F]{4}|["\\/bfnrt])')
_JSON_ESCAPED = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}
_WITHHELD_FIELD = "[REDACTED FIELD]"


def _secret_key(k):
    """The one home for "is this key secret-shaped". Normalise the key (surrounding quotes and brackets stripped,
    lowercased, every '_', '-', '.' and space removed; camelCase boundaries are only spaces, so splitting them
    changes nothing once those are removed); it is secret when any secret substring (password, passwd, pwd,
    passphrase, secret, token, credential, authorization, cookie, apikey, privatekey, secretkey, accesskey) appears
    in it. The value plays no part, and a compound key written with no separator ("dbpassword", "apikeys") is
    caught. This fails closed: "tokenizer", "passwordless" and "tokens" are secret too; _is_count_key is the one
    exemption."""
    if not isinstance(k, str):
        return False
    norm = re.sub(r"[_.\- ]+", "", k.strip(_KEY_QUOTES).lower())
    return any(s in norm for s in _SECRET_SUBSTRINGS)


def _is_count_key(k):
    """The one exemption from _secret_key: an allowlisted count key. Cut the key into words (surrounding quotes and
    brackets stripped, camelCase split, lowercased, split on '_', '-', '.' and spaces); it is a count key when the
    last word is "tokens" or the last two are "tokens count" (tokens, *_tokens, *_tokens_count). It is exempt only
    while its value is a number, which the callers check; any other value under it stays secret."""
    if not isinstance(k, str):
        return False
    words = [w for w in re.split(r"[_.\- ]+", _CAMEL_BOUNDARY.sub(" ", k.strip(_KEY_QUOTES)).lower()) if w]
    return words[-1:] == ["tokens"] or words[-2:] == ["tokens", "count"]


_NUMBER_VALUE = re.compile(r" *(?P<q>[\"']?)-?\d+(?:\.\d+)?(?P=q) *(?:[,}\]\n]|\Z)")


def _number_value_follows(text, pos):
    """True when the whole value at pos is a number: past optional spaces, an optional quote, an int or a float,
    the same closing quote if one opened, then optional spaces and a ',', '}', ']', newline or the end of the text.
    Anything else after the number, or a mismatched quote pair, is not a count."""
    return _NUMBER_VALUE.match(text, pos) is not None


def _json_strings(value):
    """Every string value and key of a parsed JSON structure, collected without recursion."""
    out, stack = [], [value]
    while stack:
        v = stack.pop()
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, list):
            stack.extend(v)
        elif isinstance(v, dict):
            for k, item in v.items():
                out.append(k)
                stack.append(item)
    return out


def _decoded_views(text):
    """The decoded views of a text: every string value and key when the whole text parses as JSON, and always the
    text with each JSON escape (n, t, r, quote, backslash, slash, b, f, uXXXX after a backslash) replaced by its
    character in one regex pass, a malformed escape left as it is."""
    views = []
    try:
        views.append("\n".join(_json_strings(json.loads(text))))
    except (ValueError, RecursionError):
        pass
    views.append(_JSON_ESCAPE.sub(
        lambda m: chr(int(m.group()[2:], 16)) if m.group()[1] == "u" else _JSON_ESCAPED[m.group()[1]], text))
    return views


def _detects(text):
    """The detector over one view: a key-like run that _secret_key accepts, then any run of characters that are not
    word characters, newlines, ':' or '=', then ':' or '=', unless it is a count key whose value is a number."""
    for m in _KEY_CANDIDATE.finditer(text):
        key = m.group("key")
        if _secret_key(key) and not (_is_count_key(key) and _number_value_follows(text, m.end())):
            return True
    return False


def _has_secret(text):
    """The one text detector: a key-like run (one word, or two joined by a space) that _secret_key accepts and
    that is followed by ':' or '=' (gap as in _detects), or a private-key block, anywhere in the text or in a decoded
    view of it (the JSON strings and keys, and the text with its JSON escapes decoded, so a literal backslash-n before
    "password: x" and a backslash-u0077 in "password" both count). A count key followed by a number is not a match
    (_is_count_key). A two-word run is judged by _secret_key on both words, so "the password: x" and "api key = x"
    count. Nothing tracks where a value ends; a text this matches is withheld whole."""
    return any(_detects(v) or bool(_PEM_BEGIN.search(v)) for v in [text, *_decoded_views(text)])


def _secret_line_count(text):
    """How many lines of the text the detector matches (1 when only the whole text matches)."""
    return sum(1 for line in text.split("\n") if _has_secret(line)) or 1


def _scrub_text(text):
    """A record string: withheld whole when it holds a credential-shaped assignment, else scrubbed of token shapes."""
    if _has_secret(text):
        return _WITHHELD_FIELD
    return pr_comment.scrub(text)


def _scrubbed(value):
    if isinstance(value, str):
        return _scrub_text(value)
    if isinstance(value, list):
        return [_scrubbed(v) for v in value]
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            hidden_key = isinstance(k, str) and (_has_secret(k) or pr_comment.scrub(k) != k)
            if hidden_key:
                n, nk = 0, "[REDACTED KEY]"
                while nk in out or nk in value:
                    n += 1
                    nk = f"[REDACTED KEY]-{n}"
                k2 = nk
            else:
                k2 = k
            counted = _is_count_key(k) and isinstance(v, (int, float)) and not isinstance(v, bool)
            secret = hidden_key or (_secret_key(k) and not counted)
            out[k2] = "[REDACTED]" if secret and v is not None else _scrubbed(v)
        return out
    return value


def _shed_why_paths(basis):
    """Step 1: the sampled paths leave the reason lines (``name (a, b, c)`` becomes ``name``)."""
    names = [t["name"] for t in basis["touched"]]
    why = [lane_call.why_line_paths_stripped(w, names) for w in basis["why"]]
    return dict(basis, why=why, whyCount=basis.get("whyCount", len(basis["why"])), basisShed="why-paths")


def _shed_matched(basis):
    """Step 2: the matched path lists go; each area keeps its name and its matchedCount."""
    touched = [dict(t, matched=[], matchedCount=t.get("matchedCount", len(t["matched"])))
               for t in basis["touched"]]
    return dict(basis, touched=touched, basisShed="matched")


def _shed_unmatchable(basis):
    """Step 3: the unmatchable list goes; unmatchableCount stays."""
    return dict(basis, unmatchable=[],
                unmatchableCount=basis.get("unmatchableCount", len(basis["unmatchable"])),
                basisShed="unmatchable")


def _shed_to_floor(basis):
    """Last resort: the floor, the lane, the first reason line and the counts."""
    out = {k: basis[k] for k in ("floor", "lane", "proposalTaken", "source") if k in basis}
    out.update(why=basis["why"][:1], whyCount=basis.get("whyCount", len(basis["why"])),
               touchedCount=basis.get("touchedCount", len(basis["touched"])),
               matchedCount=basis["matchedTotal"] if "matchedTotal" in basis
               else sum(t.get("matchedCount", len(t["matched"])) for t in basis["touched"]),
               unmatchableCount=basis.get("unmatchableCount", len(basis["unmatchable"])),
               basisShed="floor-only")
    return out


_SHED_STEPS = (_shed_why_paths, _shed_matched, _shed_unmatchable, _shed_to_floor)

_KEPT_OBSERVATION = ("read", "toolCalls")


def _shed_observation(record):
    """Reviewer step 1: each observation keeps only read and toolCalls; a row with no dict observation is left as it is."""
    rows = [dict(v, observation={k: v["observation"][k] for k in _KEPT_OBSERVATION if k in v["observation"]})
            if isinstance(v.get("observation"), dict) else v for v in record["reviewers"]]
    return dict(record, reviewers=rows)


def _shed_run_dir(record):
    """Reviewer step 2: each row's non-None runDir becomes None; a row with none is left as it is."""
    return dict(record, reviewers=[dict(v, runDir=None) if v.get("runDir") is not None else v
                                   for v in record["reviewers"]])


# Only reviewer evidence detail is shed; the status, whatIsMissing, findings' outcome and reason, go-aheads and each
# row's name, ran, planned, vendor, model, family, commit and coversFinalCommit are never touched.
_REVIEWER_STEPS = (("observation", _shed_observation), ("runDir", _shed_run_dir))
_REVIEWER_SHED_WHAT = {"observation": "engine telemetry", "runDir": "run directories"}


def _links_raw_output(record):
    """True when the record links at least one raw-output comment that was posted (not withheld)."""
    raws = record.get("rawOutputs")
    return isinstance(raws, list) and any(isinstance(x, dict) and x.get("withheld") is not True for x in raws)


def _reviewer_shed_line(record):
    """The shed line for a record whose reviewerShed lists the applied steps: it names only those steps, and points
    only at output the record links."""
    what = " and ".join(_REVIEWER_SHED_WHAT[n] for n in record["reviewerShed"])
    where = ("the reviewers' findings are in the raw-output comments linked under rawOutputs, and the trimmed "
             "engine detail is in the engines' own run records"
             if _links_raw_output(record) else "the engines' own run records hold the full output")
    return f"Reviewer detail trimmed to fit this comment ({what}); {where}."


_ROUND_SUFFIX = re.compile(r"(.*) \(round (\d+)\)", re.S)
LISTED = "(listed in the full record)"
_RAN_STATES = ("engine-record", "reported-by-session")
_ROUNDS_WORD = {"rounds": "round cap", "ceiling": "round ceiling"}
# The reviewer header's roles, their one home: a panel seat's lens, a row's phase stem (`<stem> <seat> (round n)`)
# and the order the non-lens roles are listed in.
_PANEL_LENS = {"code-reviewer": "code", "test-role": "test", "security-reviewer": "security",
               "premortem-reviewer": "premortem", "architecture-reviewer": "architecture"}
_STEM_ROLE = {"verifiers ": "verifier", "audits ": "fix auditor", "scoped-finder ": "scoped finder",
              "gap-sweep ": "gap sweep"}
_ROLE_ORDER = ("verifier", "synthesis", "fix auditor", "scoped finder", "gap sweep")
_OUTCOME_PHRASES = ("fixed", "shown wrong", "craft call", "left for the owner", "settled by a ruling")
assert len(rfs.OUTCOMES) == len(_OUTCOME_PHRASES), "every outcome needs its words in _OUTCOME_PHRASES"
_OUTCOME_WORDS = dict(zip(rfs.OUTCOMES, _OUTCOME_PHRASES))


def _seat_round(name):
    """A reviewer row's name as (seat, round): the name without its trailing ` (round <n>)` and the round, or (name, None)."""
    m = _ROUND_SUFFIX.fullmatch(name) if isinstance(name, str) else None
    return (m.group(1), int(m.group(2))) if m else (name, None)


def _row_bullet(v, final_sha):
    """The bullet for one reviewer row that carries no round suffix."""
    label = {"engine-record": "ran (engine record)", "reported-by-session": f"ran ({SESSION})"}.get(
        v["ran"], "did not run")
    if v["ran"] != "not-run" and v.get("commit") and v["commit"] != final_sha:
        label += f" on {v['commit'][:7]}"
    word = v.get("ownerWord")
    read = _read_words([v])
    return (f"- {v['name']}: {label}"
            + ("; not independent of the makers" if v.get("notIndependent") else "")
            + (f" (owner's word: {word['where']})" if v.get("notIndependent") and isinstance(word, dict)
               and isinstance(word.get("where"), str) and word["where"] else "")
            + f"; findings: {v['findingsCoverage']}" + (f"; {read}" if read else ""))


def _read_words(rows):
    """What the rows that carry a read-parts list say was read: `read <n> files, <m> lines`, `read nothing` when
    every such list is empty, None when no row carries one."""
    lists = [v["readParts"] for v in rows if isinstance(v.get("readParts"), list)]
    if not lists:
        return None
    parts = [p for part_list in lists for p in part_list]
    if not parts:
        return "read nothing"
    return (f"read {len({p['file'] for p in parts})} files, "
            f"{sum(end - start + 1 for p in parts for start, end in p['lines'])} lines")


def _rounds_text(rounds):
    nums = sorted(set(rounds))
    return ("round " if len(nums) == 1 else "rounds ") + ", ".join(str(n) for n in nums)


def _seat_bullet(seat, rows, final_sha):
    """One bullet for a seat across its rounds: the rounds it ran in, the rounds it did not, and the rest, said once."""
    buckets = {}
    for v, n in rows:
        state = v["ran"] if v["ran"] in _RAN_STATES else "not-run"
        commit = v["commit"][:7] if state != "not-run" and v.get("commit") and v["commit"] != final_sha else None
        buckets.setdefault((state, commit), []).append(n)
    said = []
    for state in (*_RAN_STATES, "not-run"):
        for (s, commit), nums in buckets.items():
            if s != state:
                continue
            where = _rounds_text(nums)
            text = {"engine-record": f"ran in {where} (engine record)",
                    "reported-by-session": f"ran in {where} ({SESSION})"}.get(s, f"did not run in {where}")
            said.append(text + (f" on {commit}" if commit else ""))
    loose = [(v, n) for v, n in rows if v.get("notIndependent")]
    if loose:
        words = list(dict.fromkeys(v["ownerWord"]["where"] for v, _ in loose
                                   if isinstance(v.get("ownerWord"), dict)
                                   and isinstance(v["ownerWord"].get("where"), str) and v["ownerWord"]["where"]))
        said.append(f"not independent of the makers in {_rounds_text([n for _, n in loose])}"
                    + (f" (owner's word: {', '.join(words)})" if words else ""))
    coverage = list(dict.fromkeys(v["findingsCoverage"] for v, _ in rows))
    said.append("findings: " + (coverage[0] if len(coverage) == 1
                                else "; ".join(f"round {n}: {v['findingsCoverage']}" for v, n in rows)))
    read = _read_words([v for v, _ in rows])
    return f"- {seat}: " + "; ".join(said + ([read] if read else []))


def _seat_groups(r):
    """The reviewer rows grouped by seat: a row named `<seat> (round <n>)` joins its seat's group, in the order
    the seats first appear; a row with no round suffix is a group of its own (keyed by a one-item tuple)."""
    seats = {}
    for i, v in enumerate(r["reviewers"]):
        seat, n = _seat_round(v["name"])
        seats.setdefault(seat if n is not None else (i,), []).append((v, n))
    return seats


def _reviewer_bullets(r):
    """One bullet per seat group; the record's JSON keeps every row."""
    final_sha = r["finalCommit"]["sha"]
    return [_row_bullet(rows[0][0], final_sha) if isinstance(key, tuple) else _seat_bullet(key, rows, final_sha)
            for key, rows in _seat_groups(r).items()]


def _plural(n, one, many):
    return f"{n} {one if n == 1 else many}"


def _refused_line(refused, compact):
    if compact:
        return f"Not taken into the review: {_plural(len(refused), 'finding', 'findings')} {LISTED}."
    reasons = {}
    for x in refused:
        reason = _clip(x.get("reason"))
        reasons[reason] = reasons.get(reason, 0) + 1
    return (f"Not taken into the review: {_plural(len(refused), 'finding', 'findings')} — "
            + "; ".join(f"{reason}: {count}" for reason, count in reasons.items()) + ".")


def _inline_code(text):
    """``text`` as a Markdown code span whose fence is longer than any backtick run inside it."""
    fence = "`" * (max((len(m) for m in re.findall(r"`+", text)), default=0) + 1)
    pad = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{fence}{pad}{text}{pad}{fence}"


def _command_refusals_line(refusals, compact):
    count = _plural(len(refusals), "refused or denied command", "refused or denied commands")
    if compact:
        return f"Refusals met: {count} {LISTED}."
    parts = []
    for x in refusals:
        by = x.get("refusedBy") + (f": {x['hook']}" if x.get("hook") else "")
        took = f", took {_inline_code(_clip(x['route']))}" if x.get("route") else ""
        parts.append(f"round {x.get('round')}: {_inline_code(_clip(x.get('command')))} ({by}{took}) → {_clip(x.get('next'))}")
    return f"Refusals met: {len(refusals)} — " + "; ".join(parts) + "."


def _rounds_line(rounds):
    if not isinstance(rounds, dict):
        return None
    cap = rounds.get("cap")
    if cap is None:
        return f"Rounds: {rounds.get('count')}."
    word = _ROUNDS_WORD.get(rounds.get("capKind"), _ROUNDS_WORD["rounds"])
    return (f"Rounds: {rounds.get('count')} of {cap} ({word})."
            + (" The loop stopped at its cap." if rounds.get("stoppedAtCap") else ""))


def _extra_audit_line(rounds, compact):
    extra = rounds.get("extraAudit") if isinstance(rounds, dict) else None
    if not isinstance(extra, dict):
        return None
    cap = rounds.get("cap")
    why = _clip(extra.get("why")) if compact else extra.get("why")
    return (f"Extra audit round: ran, ordered at the vet and not counted in the {f'{cap} ' if cap is not None else ''}"
            f"rounds: {why}.")


def _run_result(run):
    if run.get("status") == "ran":
        return "passed" if run.get("exitCode") == 0 else f"failed (exit {run.get('exitCode')})"
    return "timed out" if run.get("status") == "timed-out" else "did not start"


def _rerun_line(checks, compact):
    if not checks:
        return None
    lead = "Re-run after one failure on unchanged code: "
    if compact:
        return f"{lead}{len(checks)} checks {LISTED}."
    return lead + "; ".join(
        f"round {c.get('round')} {_inline_code(str(c.get('check')))}: "
        + " then ".join(_run_result(run) for run in c.get("runs") or []) for c in checks)


def _roles(r):
    """The reviewer header's roles: the panel lenses, then the other roles in `_ROLE_ORDER`, for the rows that
    ran and the rounds the synthesis step ran in; each role once, the groups joined by ` · `."""
    lenses, roles = [], set()
    for v in r["reviewers"]:
        if v["ran"] == "not-run":
            continue
        seat = _seat_round(v["name"])[0]
        stem = next((role for prefix, role in _STEM_ROLE.items() if seat.startswith(prefix)), None)
        if stem:
            roles.add(stem)
        elif seat in _PANEL_LENS and _PANEL_LENS[seat] not in lenses:
            lenses.append(_PANEL_LENS[seat])
    if r.get("synthesisRounds"):
        roles.add("synthesis")
    return " · ".join(([", ".join(lenses)] if lenses else []) + [role for role in _ROLE_ORDER if role in roles])


def _place_text(p):
    return p["file"] if p.get("line") is None else f"{p['file']}:{p['line']}"


def _finding_bullet(f):
    """One finding's bullet in the findings block; the parts the finding carries follow its outcome. A run's
    output text is never in the summary."""
    bullet = (f"- {' '.join(str(x) for x in (f.get('id'), f.get('severity')) if x)} · "
              + _OUTCOME_WORDS.get(f.get("outcome"), "open"))
    grade, repeat = f.get("grade"), f.get("repeatOf")
    runs, kind = f.get("breakItRuns"), f.get("kindOfMistake")
    if isinstance(grade, dict):
        bullet += f" · {grade.get('verdict')}: {grade.get('reason')}"
    if isinstance(repeat, dict):
        bullet += f" · repeat of {repeat.get('id') or str(repeat.get('findingKey'))[:12]}"
        bullet += {True: " · fix still holds", False: " · fix no longer holds"}.get(repeat.get("fixHolds"), "")
    if runs:
        bullet += f" · break-it: {len(runs)} run(s) ({', '.join(_run_result(run) for run in runs)})"
    if isinstance(kind, dict):
        bullet += f" · kind of mistake: {kind.get('kind')}"
        places = kind.get("places") or []
        if places:
            fixed = sum(1 for p in places if p.get("fixed") is True)
            bullet += (f" · also in this PR: {', '.join(_place_text(p) for p in places)} "
                       f"({'all fixed' if fixed == len(places) else f'{fixed} of {len(places)} fixed'})")
    return bullet


def _findings_lines(findings, compact):
    entries = [f for f in findings if isinstance(f, dict)] if isinstance(findings, list) else []
    if not entries:
        return []
    if compact:
        return [f"Findings: {len(entries)} {LISTED}."]
    return ["Findings:", *[_finding_bullet(f) for f in entries]]


def _outside_lines(outside, compact):
    total = sum(len(x["hits"]) for x in outside or [])
    if not total:
        return []
    if compact:
        return [f"Outside this PR ({total}) {LISTED}."]
    lines = [f"Outside this PR ({total})"]
    for x in outside:
        src = x["source"]
        words = f"from {src['name']}" if src["kind"] == "reviewer" else f"from sweep {src['sweepId']} by {src['name']}"
        lines += [f"- {h['id']} {_place_text(h)} · {h['title']} ({words})" for h in x["hits"]]
    return [*lines, "For the advisor to sort at the vet."]


def _unread_line(share):
    if not isinstance(share, dict):
        return None
    unread, countable = share["unreadLines"], share["countableLines"]
    return (f"Left unread by the slice reviewers: {unread} of {countable} countable lines"
            + (f" ({100 * unread / countable:.1f}%)" if countable > 0 else "") + ".")


def _not_checked_line(entries, compact):
    if compact:
        return (f"{_plural(len(entries), 'earlier record', 'earlier records')} could not be checked by code "
                f"{LISTED}; the vet reads them directly.")
    named = "; ".join(f"{e.get('url') or e.get('id')} ({e.get('why')})" for e in entries)
    return f"Earlier records not checked by code, which the vet reads directly: {named}."


def _findings_listed(rec):
    earlier = rec.get("findings")
    return isinstance(earlier, list) and all(isinstance(i, dict) for i in earlier)


def _withheld_line(lst, level):
    """The summary line for the paths no external reviewer read in full; None means they could not be read."""
    if not isinstance(lst, list):
        return "Withheld from reviewers: could not be read; the vet checks every changed agent-config path by hand."
    if not lst:
        return "Withheld from reviewers: none."
    lead = "Withheld from reviewers (not readable in full; the vet checks these by hand): "
    if level >= 1:
        return f"{lead}{_plural(len(lst), 'path', 'paths')} {LISTED}."
    return lead + ", ".join(lst) + "."


def _transit_line(damage, level):
    """The summary line for a record whose fields hold redacted text; None when `transitDamage` names none. Level 0
    names the paths; the compact levels give their count, and the record's JSON keeps the list."""
    fields = damage.get("redactedFields") if isinstance(damage, dict) else None
    if not (isinstance(fields, list) and fields):
        return None
    count = _plural(len(fields), "recorded field", "recorded fields")
    if level >= 1:
        return f"Transit damage: redacted text in {count} {LISTED}, so that text is lost."
    return f"Transit damage: redacted text in {count}, so that text is lost: " + ", ".join(str(f) for f in fields) + "."


def _summary(r, level):
    """The summary text. Level 0 lists everything; level 1 turns each unbounded list (what is left, who ran,
    which findings wait, which were not taken) into a count; level 2 also turns the per-seat reviewer bullets
    into one count. The record's JSON always holds the full lists."""
    lane, ci, compact = r["lane"], r["ci"], level >= 1
    left = r["leftForOwner"]
    waits = []
    if left:
        waits.append((f"{_plural(len(left), 'finding', 'findings')} left for the owner {LISTED}" if compact
                      else "findings left for the owner (" + ", ".join(left) + ")")
                     + " wait for the owner's decision")
    if r["parked"]:
        waits.append("a review with no go-ahead is parked until the owner decides")
    wider = r["rounds"].get("wider") if isinstance(r.get("rounds"), dict) else None
    wider_lines = [f"Round {w['round']} looked wider than the last fixes: {w['why']}"
                   for w in wider or [] if isinstance(w, dict)]
    waits_text = ("Waiting for the owner: " + "; ".join(waits) + ".") if waits else "Nothing waits for the owner."
    checked = list(r["checked"][:2])
    missing = r["whatIsMissing"]
    if compact:
        ran = sum(1 for v in r["reviewers"] if v["ran"] != "not-run")
        checked = checked[:1] + ([f"Reviewers that ran: {_plural(ran, 'reviewer', 'reviewers')} {LISTED}"]
                                 if len(checked) > 1 else [])
        left_text = f"{_plural(len(missing), 'item', 'items')} {LISTED}" if missing else "nothing"
    else:
        left_text = "; ".join(missing) or "nothing"
    if r["status"] == AWAITS_OWNER:
        head = (f"reviewed; {_plural(len(left), 'finding', 'findings')} {'waits' if len(left) == 1 else 'wait'} for your decision "
                + (LISTED if compact else "(" + ", ".join(left) + ")"))
    else:
        head = r["status"].replace("-", " ")
    reason = lane.get("reason")
    if compact and reason:
        reason = _clip(reason)
    floor_line = (f"Risk floor: {r['laneBasis']['floor'] or 'none'} — " + "; ".join(r["laneBasis"]["why"]) + ".")
    if level >= 2:
        groups = _seat_groups(r)
        who = [f"Reviewers: {_plural(len(r['reviewers']), 'row', 'rows')} across "
               f"{_plural(len(groups), 'seat', 'seats')} {LISTED}."]
        roles_line = None
    else:
        roles = _roles(r)
        roles_line = f"Reviewers: {roles}" if roles else "Reviewers:"
        who = [roles_line, *_reviewer_bullets(r)]
    rounds_line = _rounds_line(r.get("rounds"))
    extra_audit_line = _extra_audit_line(r.get("rounds"), compact)
    rerun_line = _rerun_line(r.get("rerunChecks"), compact)
    findings_lines = _findings_lines(r.get("findings"), compact)
    outside_lines = _outside_lines(r.get("outsideThisPR"), compact)
    unread_line = _unread_line(r.get("unreadShare"))
    # the lines that carry reviewer or session text, left out of the claim check by the line objects built here
    quoted_lines = [*findings_lines, *outside_lines, *([roles_line] if roles_line else [])]
    refused = r.get("refused") or []
    withheld_line = _withheld_line(r.get("withheldFromReviewers"), level)
    transit_line = _transit_line(r.get("transitDamage"), level)
    command_refusals_rec = r.get("commandRefusals") or []
    refusals_line = _command_refusals_line(command_refusals_rec, compact) if command_refusals_rec else None
    lines = [
        f"**Review record: {head}.** Checked: " + "; ".join(checked) + ". Left: " + left_text + ".",
        waits_text,
        f"Lane: {lane['value']} ({lane['source']})" + (f", because {reason}" if reason else "")
        + (f" ({lane['reasonSource']})" if reason and lane.get("reasonSource") else "") + ".",
        floor_line,
        withheld_line,
        # axis: the transit-damage line is present whenever a recorded field holds redacted text — see bite-proof record wo1_2121_redacted
        *([transit_line] if transit_line else []),
        *(["Makers: " + ", ".join(m["family"] for m in r["makers"]) + "."] if r["makers"] else []),
        f"CI on the final commit {(r['finalCommit']['sha'] or 'unknown')[:7]}: {ci['state']} ({ci['source']}).",
        *([rounds_line] if rounds_line else []),
        *([extra_audit_line] if extra_audit_line else []),
        *([rerun_line] if rerun_line else []),
        *([_refused_line(refused, compact)] if refused else []),
        *([refusals_line] if refusals_line else []),
        *([_not_checked_line(r["earlierRecordsNotChecked"], compact)] if r.get("earlierRecordsNotChecked") else []),
        *who,
        *[f"Not run: {n['name']}, because {n['why']}." for n in r.get("seatsNotRun") or []],
        # axis: the shed line is present whenever a reviewer step ran — see bite-proof record wo_d_1795_reviewer-shed
        *([_reviewer_shed_line(r)] if r.get("reviewerShed") else []),
        *wider_lines,
        *findings_lines,
        *outside_lines,
        *([unread_line] if unread_line else [])]
    # The Risk floor line is the one place the lane basis's literal data (area names, sampled changed paths)
    # appears, so it alone is left out of the claim check (the line itself, never a string match), as the JSON
    # block is. Every other line is still checked.
    # The wider lines carry the driver's own reason text, and the withheld line carries literal path data,
    # like the floor line. The refusals line carries the agent's literal command and next-step text. The transit
    # line carries the recorded fields' literal paths (record keys), so it is left out too.
    # The findings block, the outside list and the reviewer header carry reviewers' and the session's own text, so
    # they are left out too, by the line objects built above.
    # axis: the refusals line's literal command text is left out of the claim check — see bite-proof record wo3_2011_record
    # axis: the findings block and the outside list are left out of the claim check, by line object — see bite-proof record c1l1_wo_a_record_seam
    _assert_no_bug_free_claim(
        "\n".join(l for l in lines if l is not floor_line and l is not withheld_line and l is not refusals_line
                  and l is not transit_line and l not in wider_lines and all(l is not q for q in quoted_lines)))
    return "\n".join(lines)


def _redacted_paths(value):
    """The path of every string value or dict key holding `[REDACTED`, in document order (dict insertion order, list
    order), collected without recursion: dict keys joined with '.', list indexes as `[i]`, a matching key reporting
    the path that ends in it. The record's own top-level `transitDamage` is skipped. No path repeats."""
    out, seen, stack = [], set(), [("", value, True, False)]
    while stack:
        path, v, top, hit = stack.pop()
        if hit or (isinstance(v, str) and "[REDACTED" in v):
            if path not in seen:
                seen.add(path)
                out.append(path)
        elif isinstance(v, list):
            stack.extend(reversed([(f"{path}[{i}]", item, False, False) for i, item in enumerate(v)]))
        elif isinstance(v, dict):
            kids = []
            for k, item in v.items():
                if top and k == "transitDamage":
                    continue
                kpath = f"{path}.{k}" if path else str(k)
                # a matching key is recorded before its value's paths: its marker entry sits ahead of the value
                if isinstance(k, str) and "[REDACTED" in k:
                    kids.append((kpath, None, False, True))
                kids.append((kpath, item, False, False))
            stack.extend(reversed(kids))
    return out


def _flag_redactions(r):
    """The record with `transitDamage.redactedFields` listing every recorded field whose text holds `[REDACTED`
    (merged into an existing `transitDamage` dict), or the record itself when no field does."""
    paths = _redacted_paths(r)
    if not paths:
        return r
    existing = r.get("transitDamage")
    return dict(r, transitDamage={**(existing if isinstance(existing, dict) else {}), "redactedFields": paths})


def _record_json(r):
    # Every "/" is written "\/" (a valid JSON escape, same values), so no bare "://" is left for a host that
    # rewrites bare URLs in transit to wrap. A "/" occurs in the dump only inside a string, and a backslash there
    # is already dumped as "\\", so the replace is exact.
    return json.dumps(r, sort_keys=True, separators=(",", ":")).replace("/", "\\/")


def _part_body(piece):
    fence = "`" * max(3, max((len(m) for m in re.findall(r"`+", piece)), default=0) + 1)
    return f"{PART_MARKER}\n{fence}json\n{piece}\n{fence}"


def _part_bodies(text):
    """The compact JSON text as part-comment bodies, each at most MAX_BODY_CHARS, in order."""
    bodies, at = [], 0
    while at < len(text):
        size = MAX_BODY_CHARS - 200
        while True:
            piece = text[at:at + size]
            body = _part_body(piece)
            if len(body) <= MAX_BODY_CHARS:
                break
            # the fence grows with the piece's longest backtick run, so the overflow can exceed the piece:
            # never step below half, so the size stays positive and the loop advances
            size = max(size - (len(body) - MAX_BODY_CHARS), size // 2, 1)
        bodies.append(body)
        at += len(piece)
    return bodies


class _Plan:
    """What a record posts as: `parts` (the part-comment bodies, empty when the record fits one comment) and
    `head(part_ids)`, the head comment's body once the parts' comment ids are known."""

    def __init__(self, parts, head):
        self.parts, self.head = parts, head


def render_plan(record):
    r = _scrubbed(record)

    def single(r):
        # axis: the redacted-field flag is computed on the record as posted, after each shed step — see bite-proof record wo1_2121_redacted
        r = _flag_redactions(r)
        return (f"{MARKER}\n{_summary(r, 0)}\n\n<details><summary>Full record</summary>\n\n```json\n"
                f"{_record_json(r)}\n```\n</details>")

    # The size bound is on what is posted (the JSON-escaped body), so it is measured here: shed the lane
    # basis's path evidence in a fixed order until the body fits. The floor, lane and proposalTaken never change.
    body = single(r)
    for step in _SHED_STEPS:
        if len(body) <= MAX_BODY_CHARS:
            break
        r = dict(r, laneBasis=step(r["laneBasis"]))
        body = single(r)
    # Then, still over the cap, the reviewers' evidence detail, one step at a time, each said on the record.
    # axis: the reviewer steps run while the body is over the cap — see bite-proof record wo_d_1795_reviewer-shed
    # A step counts as applied, and is named, only when it changed a row; one that changed nothing is not listed.
    for name, step in _REVIEWER_STEPS:
        if len(body) <= MAX_BODY_CHARS:
            break
        shed = step(r)
        if shed["reviewers"] == r["reviewers"]:
            continue
        r = dict(shed, reviewerShed=[*r.get("reviewerShed", []), name])
        body = single(r)
    if len(body) <= MAX_BODY_CHARS:
        return _Plan([], lambda part_ids=None: body)
    # Still over the cap after every step: the JSON text goes to part comments, never cut and never refused.
    r = _flag_redactions(r)  # the parts text and the head's summary carry the flag too
    text = _record_json(r)
    parts = _part_bodies(text)
    digest, chars = hashlib.sha256(text.encode("utf-8")).hexdigest(), len(text)

    def head(part_ids):
        index = json.dumps({"schema": PARTS_SCHEMA, "parts": list(part_ids), "sha256": digest, "chars": chars},
                           sort_keys=True, separators=(",", ":"))
        note = (f"The full record is in {_plural(len(part_ids), 'part comment', 'part comments')} posted just before "
                f"this one (comment ids {', '.join(str(i) for i in part_ids)}); the block below names them and "
                "carries the hash that checks them.")
        # A head over the cap takes the compact summary, then the one-count reviewer line; the full lists
        # stay in the record's parts.
        for level in (0, 1, 2):
            out = (f"{MARKER}\n{_summary(r, level)}\n\n{note}\n\n<details><summary>Full record (in parts)</summary>"
                   f"\n\n```json\n{index}\n```\n</details>")
            if len(out) <= MAX_BODY_CHARS:
                return out
        # Defensive: a head that cannot fit even with the compact summary is refused before anything is posted.
        raise Refusal("review-record-too-large", f"the record's head comment alone is {len(out)} characters")
    head([10 ** 15] * len(parts))  # the head must fit before any comment is created
    return _Plan(parts, head)


def render(record, part_ids=None):
    """The record's comment body: the whole record when it fits one comment, else the head comment that names its
    parts (with `part_ids`, or stand-in ids when none are given)."""
    plan = render_plan(record)
    return plan.head(part_ids if part_ids is not None else [10 ** 15] * len(plan.parts))


def render_raw(name, text):
    """A raw-output comment as (body, withheld). One reviewer's output file goes verbatim under a short intro,
    unless it holds a credential-shaped assignment or a private-key block: then none of it is posted."""
    if _has_secret(text):
        note = (f"Raw output of one reviewer withheld: {name}. It contains credential-shaped assignments on "
                f"{_secret_line_count(text)} line(s), so it is not posted. Its findings are in the review record on this PR.")
        _assert_no_bug_free_claim(note)
        return f"{RAW_MARKER}\n{note}", True
    intro = (f"Raw output of one reviewer, kept verbatim: {name}. "
             "A review record on this PR links this comment.")
    # Only the sentence this writer authors is checked: the kept text is the reviewer's own.
    _assert_no_bug_free_claim(intro)
    text = pr_comment.scrub(text)
    fence = "`" * max(3, max((len(m) for m in re.findall(r"`+", text)), default=0) + 1)
    body = f"{RAW_MARKER}\n{intro}\n\n{fence}\n{text}\n{fence}"
    if len(body) > GITHUB_MAX_CHARS:
        raise Refusal("review-record-too-large", f"the raw output file {name} is {len(body)} characters")
    return body, False


def _json_block(body):
    """The JSON object in a comment's closing details block, or None. The JSON text holds no raw newline, so the
    last json fence is the block's own, whatever text the summary above it carries."""
    try:
        obj = json.loads(body[body.rindex("```json\n") + 8:body.rindex("\n```\n</details>")])
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


# A host may append an attribution footer to every comment it posts: a cloud session adds
# "\n\n---\n_Generated by …_" after the closing fence. Only that one footer line is dropped; it is never
# part of the slice, and the parts' length and hash check still guards everything that is.
_HOST_FOOTER = re.compile(r"\n\n---\n_Generated by [^\n`]*_\n?\Z")


def _part_slice(body):
    """The slice of JSON text in a part comment, or None when the comment is not a well-formed part."""
    if not isinstance(body, str) or not body.startswith(PART_MARKER + "\n"):
        return None
    rest = body[len(PART_MARKER) + 1:]
    first, _, tail = rest.partition("\n")
    opened = re.fullmatch(r"(`{3,})json", first)
    if not opened:
        return None
    closing = "\n" + opened.group(1)
    if not tail.endswith(closing):
        # axis: a host-appended footer after the closing fence is dropped; any other trailing text stays unreadable
        footer = _HOST_FOOTER.search(tail)
        if not footer or not tail[:footer.start()].endswith(closing):
            return None
        tail = tail[:footer.start()]
    return tail[:len(tail) - len(closing)]


def _resolve_parts(index, by_id):
    """The record a parts head names: its part comments fetched by id, their slices joined in the listed order, and
    the text checked against the head's length and hash. None when a part is missing or malformed, the index is
    malformed, or the text does not parse as a record; a record whose length or hash differs is read and marked."""
    ids, digest, chars = index.get("parts"), index.get("sha256"), index.get("chars")
    # axis: a malformed index (no parts, a hash that is not 64 hex digits, a negative or non-integer length) refuses
    if not (isinstance(ids, list) and ids and all(isinstance(i, int) and not isinstance(i, bool) for i in ids)
            and isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest)
            and isinstance(chars, int) and not isinstance(chars, bool) and chars >= 0 and by_id):
        return None
    pieces = []
    for pid in ids:
        piece = _part_slice((by_id.get(pid) or {}).get("body")) if not isinstance(pid, bool) else None
        if piece is None:
            return None
        pieces.append(piece)
    text = "".join(pieces)
    try:
        rec = json.loads(text)
    except ValueError:
        return None
    if not (isinstance(rec, dict) and rec.get("schema") == RECORD_SCHEMA):
        return None
    # axis: parts changed in transit that still parse as a record are read and reported, never refused; the length
    # and hash say only that something changed, so the reader names it for the vet instead of hiding the record
    hash_matches = hashlib.sha256(text.encode("utf-8")).hexdigest() == digest
    if len(text) != chars or not hash_matches:
        # merged into a `transitDamage` the writer already put there (its redacted fields), never replacing it
        damage = rec.get("transitDamage")
        rec = dict(rec, transitDamage={**(damage if isinstance(damage, dict) else {}), "recordedChars": chars,
                                       "foundChars": len(text), "hashMatches": hash_matches})
    return rec


def _parse_body(body, by_id=None):
    """The record in a record comment, or None: a whole record is read from the comment itself, a parts head from
    the part comments `by_id` (comment id to comment) holds."""
    obj = _json_block(body)
    if obj is None:
        return None
    if obj.get("schema") == RECORD_SCHEMA:
        return obj
    return _resolve_parts(obj, by_id) if obj.get("schema") == PARTS_SCHEMA else None


def _span(text, offset):
    """The excerpt of `text` at most 40 characters either side of `offset`, as a JSON string."""
    return json.dumps(text[max(0, offset - 40):offset + 40])


def _unreadable_detail(latest, by_id):
    """Why the latest record comment is unreadable, in a short phrase: the comment's url (or a stand-in), then where
    the JSON text first fails to parse (character offset in the comment body that holds it, with an excerpt), or the
    other cause. Only the refusal path calls it."""
    where = latest.get("url") or "the existing record"
    body = latest.get("body")
    try:
        start, end = body.rindex("```json\n") + 8, body.rindex("\n```\n</details>")
    except (AttributeError, ValueError):
        return f"{where}: the comment has no JSON block"
    try:
        obj = json.loads(body[start:end])
    except json.JSONDecodeError as e:
        return f"{where}: the record's JSON does not parse at character {start + e.pos} of comment " \
               f"{latest.get('id')}: {_span(body, start + e.pos)}"
    if not isinstance(obj, dict) or obj.get("schema") not in (RECORD_SCHEMA, PARTS_SCHEMA):
        return f"{where}: the JSON is not a review record"
    if obj.get("schema") == RECORD_SCHEMA:
        return f"{where}: the record could not be read"
    ids = obj.get("parts")
    if not (isinstance(ids, list) and ids and all(isinstance(i, int) and not isinstance(i, bool) for i in ids)):
        return f"{where}: the parts index is malformed"
    pieces = []
    for pid in ids:
        piece = _part_slice((by_id.get(pid) or {}).get("body"))
        if piece is None:
            return f"{where}: part comment {pid} is missing or malformed"
        pieces.append(piece)
    text = "".join(pieces)
    try:
        rec = json.loads(text)
    except json.JSONDecodeError as e:
        pos = e.pos
        for pid, piece in zip(ids, pieces):
            if pos < len(piece) or pid == ids[-1]:
                break
            pos -= len(piece)
        part = by_id[pid]["body"]
        offset = part.index("\n", len(PART_MARKER) + 1) + 1 + pos
        return f"{where}: the record's JSON does not parse at character {offset} of comment {pid}: " \
               f"{_span(part, offset)}"
    if not (isinstance(rec, dict) and rec.get("schema") == RECORD_SCHEMA):
        return f"{where}: the joined parts are not a review record"
    return f"{where}: the parts index is malformed"


def _comments(rd, pr, repo):
    comments = rd["list_comments"](pr, repo)
    if comments is None:
        raise Refusal("review-record-gh-failed", "the PR comments could not be listed")
    return comments


def _marker_comments(comments):
    """The record comments among a PR's comments, oldest first (comment ids only grow)."""
    # axis: a part comment is never a record, so it is never the latest record — see bite-proof record c7l3_wo1_record_writer
    return sorted((c for c in comments if str(c.get("body", "")).startswith(MARKER)), key=lambda c: c["id"])


def _guarded(fn):
    try:
        return fn()
    except Refusal as e:
        return _refuse(e.reason, e.detail)
    except Exception as e:  # nothing raises to the caller
        return _refuse("review-record-internal-error", f"{type(e).__name__}: {e}")


def write(account_path, repo_root, readers=None):
    def go():
        try:
            with open(account_path, encoding="utf-8") as fh:
                account = json.load(fh)
        except (OSError, ValueError):
            raise Refusal("review-account-invalid", "account file")
        account = dict(account, repoRoot=repo_root) if isinstance(account, dict) else account
        rd = _readers(readers)
        a = _validate(account)
        if a["repo"] is None:
            # Bind every GitHub call to the repo root's repository, before the first one.
            repo = rd["repo_name"](repo_root)
            if not (isinstance(repo, str) and _REPO_RE.fullmatch(repo)):
                raise Refusal("review-record-gh-failed", "the repository could not be resolved from the repo root")
            a = dict(a, repo=repo)
        pr, repo = a["pr"], a["repo"]
        texts, raw_reader = {}, rd["read_text"]  # one read per raw file, so the readability check and the posted text agree

        def read_text(path):
            if path not in texts:
                texts[path] = raw_reader(path)
            return texts[path]
        rd = dict(rd, read_text=read_text)
        comments = _comments(rd, pr, repo)
        by_id = {c["id"]: c for c in comments}
        found = _marker_comments(comments)
        latest = found[-1] if found else None
        prior, not_checked = None, []
        for c in found:
            parsed = _parse_body(c["body"], by_id)
            # a record whose findings list is malformed is as unreadable as one that does not parse
            usable = parsed if parsed is not None and _findings_listed(parsed) else None
            # axis: every earlier record code could not check (unreadable, changed in transit, or holding redacted
            # text) is listed on each new record, so a later write never hides it from the vet, who reads only the
            # latest record — see bite-proof record wo1_2121_redacted
            damage = usable.get("transitDamage") if usable is not None else None
            if usable is None or damage:
                if usable is None:
                    why = "unreadable"
                elif isinstance(damage, dict) and list(damage) == ["redactedFields"]:
                    why = "redacted text"
                else:
                    why = "changed in transit"
                not_checked.append({"id": c["id"], "url": c.get("url"), "why": why})
            if c is latest:
                # axis: an unreadable earlier record never blocks a new one; it is listed instead
                prior = usable
        missing = _unaccounted(prior, a["findings"])
        if missing:
            raise Refusal("review-record-unaccounted",
                          "earlier findings with no outcome in this account: " + ", ".join(missing))
        record = build_record(a, rd, prior=prior)
        record["earlierRecordsNotChecked"] = not_checked
        raws = [(os.path.basename(p), *render_raw(os.path.basename(p), read_text(p)))
                for p in a["rawFindingsFiles"] if str(p) not in record["unreadFiles"]]
        previous = {"id": latest["id"], "url": latest.get("url")} if latest else None
        # Refuse here, before any comment is created, if the record cannot be posted: the head comment, sized with
        # stand-in comment ids, must fit.
        render_plan(dict(record, previousRecord=previous and {"id": 10 ** 15, "url": "u" * 120},
                         rawOutputs=[{"file": n, "id": 10 ** 15, "url": "u" * 120, "withheld": w} for n, _, w in raws]))
        links = []
        for name, body, withheld in raws:
            sent = rd["create_comment"](pr, repo, body)
            if sent is None:
                raise Refusal("review-record-gh-failed", f"the raw output comment for {name} could not be written")
            links.append({"file": name, "id": sent["id"], "url": sent.get("url"), "withheld": withheld})
        record.update(rawOutputs=links, previousRecord=previous)
        plan = render_plan(record)
        # The parts go up before the head: a write that stops part-way leaves parts no head names, never a half record.
        part_ids = []
        for n, body in enumerate(plan.parts, 1):
            sent = rd["create_comment"](pr, repo, body)
            if sent is None:
                raise Refusal("review-record-gh-failed", f"part {n} of {len(plan.parts)} of the record could not be written")
            part_ids.append(sent["id"])
        sent = rd["create_comment"](pr, repo, plan.head(part_ids))
        if sent is None:
            raise Refusal("review-record-gh-failed", "the record comment could not be written")
        return {"ok": True, "action": "created", "url": sent.get("url"), "parts": len(part_ids),
                "status": record["status"], "parked": record["parked"], "whatIsMissing": record["whatIsMissing"]}
    return _guarded(go)


def read(pr, repo=None, readers=None):
    def go():
        rd = _readers(readers)
        comments = _comments(rd, pr, repo)
        found = _marker_comments(comments)
        if not found:
            raise Refusal("review-record-missing", f"no review record on PR {pr}")
        latest = found[-1]
        by_id = {c["id"]: c for c in comments}
        rec = _parse_body(latest["body"], by_id)
        if rec is None:
            raise Refusal("review-record-unreadable", _unreadable_detail(latest, by_id))
        return {"ok": True, "url": latest.get("url"), **rec, "earlierRecords": [c.get("url") for c in found[:-1]]}
    return _guarded(go)


def _shows_reading(run):
    obs = run.get("observation") if isinstance(run, dict) else None
    # the record writer credits a run only when it is a graded review: hold the reading to the same rule
    return (isinstance(run, dict) and run.get("graded") is True
            and run.get("runKind") == session_contract.RUN_KIND_REVIEW
            and isinstance(obs, dict) and obs.get("read") == "engaged")


def _move_up_blocker(seat_map, maker_families, lane_basis=None):
    """The first reason a seat map does not let a second no-reading review move up to the full lane, else None.
    The panel it must hold is the one the lane basis calls for; with no basis, the full risky panel."""
    roster = seat_map.get("roster") if isinstance(seat_map, dict) else None
    if not isinstance(roster, list) or not roster:
        return "the seat map has no roster"
    # axis: a map composed for fewer seats than the lane basis calls for cannot show the whole panel independent, so it parks — see bite-proof record wo_a_1797_roster
    missing = [n for n in seat_map_module.roster_for(lane_basis) if n not in roster]
    if missing:
        return "the seat map's roster omits a panel seat: " + ", ".join(missing)
    seats = seat_map.get("seats")
    if not isinstance(seats, dict) or not all(isinstance(seats.get(n), dict) for n in roster):
        return "the seat map has no entry for a roster seat"
    # axis: a roster seat that is unfilled, or whose family is a maker's, cannot be shown independent, so the lane is parked, never moved up — see bite-proof record wo_a_1796_reading-independence
    if any(seat_map_module.is_unfilled(seats[n]) for n in roster):
        return "a roster seat in the seat map is unfilled"
    if not all(isinstance(seats[n].get("family"), str) and seats[n]["family"] for n in roster):
        return "a roster seat in the seat map names no family"
    if not maker_families:
        return "no maker is named, so independence cannot be shown"
    if any(seats[n]["family"] in maker_families for n in roster):
        return "a roster seat in the seat map is from a maker's family"
    if not all(isinstance(seats[n].get(k), str) and seats[n][k] for n in roster for k in ("vendor", "model")):
        return "a roster seat in the seat map names no vendor or model"
    return None


def reading_next(runs, seat_map, maker_families, lane_basis=None):
    """What follows a review whose reading is not shown: accept, rerun, move-up or park. Pure: no model call, no write.
    The lane basis is the one given, else the one the seat map carries from its compose."""
    runs = list(runs)[:2]
    if any(_shows_reading(run) for run in runs):
        return {"next": "accept", "reason": "the engine's record shows that the reviewer read the change"}
    if not runs:
        return {"next": "park", "reason": "no run was given, so no reading can be shown"}
    if len(runs) < 2:
        return {"next": "rerun", "reason": "the one run does not show that the reviewer read the change"}
    if lane_basis is None and isinstance(seat_map, dict):
        lane_basis = seat_map.get("laneBasis")
    blocker = _move_up_blocker(seat_map, frozenset(maker_families), lane_basis)
    if blocker:
        return {"next": "park", "reason": blocker}
    return {"next": "move-up", "reason": "two runs do not show a reading and the seat map holds independent seats"}


def _read_seat_map(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (TypeError, OSError, ValueError):
        return None


def main(argv=None):
    parser = argparse.ArgumentParser(prog="review_record")
    sub = parser.add_subparsers(dest="command", required=True)
    w = sub.add_parser("write")
    w.add_argument("--account", required=True)
    w.add_argument("--repo-root", required=True, dest="repo_root")
    r = sub.add_parser("read")
    r.add_argument("--pr", type=int, required=True)
    r.add_argument("--repo", default=None)
    n = sub.add_parser("reading-next")
    n.add_argument("--run-dir", action="append", default=[], dest="run_dirs")
    n.add_argument("--seat-map", default=None, dest="seat_map")
    n.add_argument("--maker-family", action="append", default=[], dest="maker_families")
    args = parser.parse_args(argv)
    if args.command == "reading-next":
        runs = [_engine_run(d)[0] for d in dict.fromkeys(os.path.realpath(d) for d in args.run_dirs)]
        print(json.dumps(reading_next(runs, _read_seat_map(args.seat_map), args.maker_families)))
        return 0
    result = write(args.account, args.repo_root) if args.command == "write" else read(args.pr, args.repo)
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
