#!/usr/bin/env python3
"""The review record: one marker-tagged PR comment per review session, decided in one place.

A write only creates. It adds one new record comment, plus one new comment per raw reviewer output
file, and never edits a comment. The record links the record before it (previousRecord) and each raw
comment (rawOutputs), so everything stays retrievable. The one thing a write reads from an earlier
record is the identity key of each finding in the latest one (_unaccounted): every such key must
appear in the new account's findings with an outcome, or the write refuses before anything is posted.

build_record() is the only place a status, a reviewer's ran-state or a code fact is decided;
write() is the only path that posts, and read() does I/O only. Facts that code holds (lane, final
commit, CI, whether a reviewer with a run directory ran on the final commit) come from code, never
from the session's account.

CLI:
  review_record.py write --account FILE --repo-root DIR
  review_record.py read --pr N [--repo OWNER/NAME]
  review_record.py reading-next --run-dir A [--run-dir B] [--seat-map FILE] --maker-family F [--maker-family F ...]
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
import lane_call  # noqa: E402
import model_registry  # noqa: E402
import pr_comment  # noqa: E402
import review_findings_schema as rfs  # noqa: E402
import seat_map as seat_map_module  # noqa: E402
import session_contract  # noqa: E402
import store_core  # noqa: E402

MARKER = "<!-- superheroes:review-record -->"
RAW_MARKER = "<!-- superheroes:review-raw-output -->"
ACCOUNT_SCHEMA = "review-account/1"
RECORD_SCHEMA = "review-record/1"
FORBIDDEN_CLAIMS = ("no bugs", "bug-free", "bug free")
MAX_BODY_CHARS = 65000
GITHUB_MAX_CHARS = 65536
SESSION = "reported by the session"
_LEFT_FOR_OWNER = rfs.LEFT_FOR_OWNER
_RED = frozenset({"failure", "timed_out", "cancelled", "action_required", "startup_failure", "stale"})
# GitHub lists at most 3000 files for a pull request; a list this long may be cut short.
_FILES_CEILING = 3000
_LANE_RE = re.compile(
    r"(?m)^\*\*Lane call:\*\*\s*(" + "|".join(re.escape(lane) for lane in lane_call.LANES) + r")\b[.:]?[ \t]*(.*)$"
)
_REPO_RE = re.compile(r"[^/\s]+/[^/\s]+")
_VENDOR_MODELS = {"claude": model_registry.claude_models, "codex": model_registry.codex_models,
                  "cursor": model_registry.cursor_models}


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


def _gh_json(*args):
    out = _run(["gh", *args])
    try:
        return None if out is None else json.loads(out)
    except ValueError:
        return None


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


def _check_data(sha, repo):
    base = _api(repo, f"commits/{sha}")
    out = _run(["gh", "api", base + "/check-runs?per_page=100", "--paginate"])
    status = _gh_json("api", base + "/status")
    try:
        # Every page, merged: a failed page read leaves CI unavailable, never green on a partial read.
        runs = {"check_runs": [r for page in pr_comment._parse_paginated_arrays(out) for r in page["check_runs"]]}
    except (ValueError, KeyError, TypeError):
        return None
    return (runs, status) if isinstance(status, dict) else None


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
    out = _run(["gh", "api", _api(repo, f"issues/{pr}/comments"), "--paginate"])
    try:
        return None if out is None else [
            {"id": c["id"], "author": c["user"]["login"], "body": c["body"], "url": c["html_url"]}
            for c in pr_comment._parse_paginated_arrays(out)]
    except (ValueError, KeyError, TypeError):
        return None


def changed_paths(pr, repo):
    """Every path the PR changes, as a list, or None when the list cannot be trusted to be complete:
    a failed call or parse, an entry with no string filename, or GitHub's file ceiling reached.
    Removed files are kept (a deletion inside a risk area touches it), and so is each renamed
    file's previous name (a rename out of a risk area still touches it)."""
    out = _run(["gh", "api", _api(repo, f"pulls/{pr}/files"), "--paginate"])
    try:
        files = None if out is None else pr_comment._parse_paginated_arrays(out)
    except ValueError:
        return None
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


def _create_comment(pr, repo, body):
    return _send("POST", _api(repo, f"issues/{pr}/comments"), body)


def _readers(overrides):
    return {"pr_meta": _pr_meta, "issue_body": _issue_body, "check_data": _check_data,
            "lane_marker": _lane_marker, "engine_run": _engine_run, "list_comments": _list_comments,
            "create_comment": _create_comment, "repo_name": _repo_name, "read_text": _read_text,
            "changed_paths": changed_paths, **(overrides or {})}


# --- the account ---

def _step_ok(v):
    return v is None or (isinstance(v, int) and not isinstance(v, bool))


def _makers_for(makers, step):
    """Families that were makers of what a reviewer at `step` reviewed: a maker with a `fromStep` joined
    only after earlier steps, so a reviewer before that step is judged against the makers it faced. A
    reviewer with no step, or a maker with no `fromStep`, counts in full."""
    return frozenset(m["family"] for m in makers
                     if m.get("fromStep") is None or step is None or step >= m["fromStep"])


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
    chk(isinstance(a.get("reviewers"), list) and a["reviewers"], "reviewers")
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
        chk(sn(f.get(rfs.CONSEQUENCE_KEY)), f"findings[{i}].{rfs.CONSEQUENCE_KEY}")
    for k in ("rawFindingsFiles", "checked"):
        chk(all(ne(x) for x in lst(k)), k)
    for i, g in enumerate(lst("goAheads")):
        chk(isinstance(g, dict) and ne(g.get("reviewer")) and g.get("kind") in ("standing-ruling", "owner-words"),
            f"goAheads[{i}]")
    rounds = a.get("rounds", {"count": 0, "cap": None, "stoppedAtCap": False})
    chk(isinstance(rounds, dict) and isinstance(rounds.get("count"), int)
        and (rounds.get("cap") is None or isinstance(rounds["cap"], int))
        and isinstance(rounds.get("stoppedAtCap"), bool), "rounds")
    return {"repo": None, "lane": None, "laneReason": None, "finalCommit": None, "ci": None,
            "findings": [], "rawFindingsFiles": [], "goAheads": [], "checked": [], "makers": [], **a,
            "makers": makers or [], "rounds": rounds}


# --- code facts ---

def ci_state(check_runs, status):
    runs = (check_runs or {}).get("check_runs") or []
    status = status or {}
    # A status with total_count 0 reports "pending" while nothing is pending: no statuses at all.
    states = ([status.get("state")] + [s.get("state") for s in status.get("statuses") or []]
              if (status.get("total_count") or 0) > 0 else [])
    if not runs and not states:
        return "none"
    if any(r.get("conclusion") in _RED for r in runs) or any(s in ("failure", "error") for s in states):
        return "red"
    if any(r.get("status") != "completed" for r in runs) or "pending" in states:
        return "pending"
    return "green"


def _ci(rd, repo, sha):
    data = rd["check_data"](sha, repo) if sha else None
    if data is None:
        return {"state": "none", "sha": None, "source": "unavailable"}
    return {"state": ci_state(*data), "sha": sha, "source": "GitHub checks"}


def _lane_call(a, rd, meta):
    """The first lane-call line in the PR's closing issues' bodies, then the PR body, as (match, source)."""
    if meta:
        texts = [(rd["issue_body"](n, a["repo"]), "issue lane call") for n in meta["issues"]]
        for body, source in texts + [(meta["body"], "PR lane call")]:
            hit = _LANE_RE.search(body or "")
            if hit:
                return hit, source
    return None, None


def _lane(a, rd, meta):
    m = rd["lane_marker"](a.get("repoRoot"))
    hit, source = _lane_call(a, rd, meta)
    if isinstance(m, dict) and m.get("schema") == build_lane.BUILD_LANE_SCHEMA and m.get("lane") == "full" \
            and m.get("branch") == m.get("currentBranch") and meta \
            and str(m.get("issue")) in {str(n) for n in meta["issues"]}:
        # The marker decides the value only; a reason is shown with where it came from, never as a fact code holds.
        if hit and hit.group(2).strip():
            reason, reason_source = hit.group(2).strip(), source
        elif a["laneReason"]:
            reason, reason_source = a["laneReason"], SESSION
        else:
            reason, reason_source = None, None
        return {"value": "full", "source": "build lane marker", "reason": reason, "reasonSource": reason_source}
    if hit:
        return {"value": hit.group(1), "source": source, "reason": hit.group(2).strip() or None}
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


def _finding_lines(findings):
    lines = []
    for f in findings:
        if f.get("outcome") not in rfs.OUTCOMES:
            lines.append(f"finding {_name(f)} has no outcome")
        elif not f.get("reason"):
            lines.append(f"finding {_name(f)} has no reason")
        elif f["outcome"] == _LEFT_FOR_OWNER:
            lines.append(f"finding {_name(f)} waits for the owner's decision")
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
        lines.append(f"CI is {ci['state']} on {s7(ci['sha'])}")
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
    return ("not-reviewed" if lines else "reviewed"), any(m["goAhead"] is None for m in rec["missingReviews"]), lines


def build_record(account, readers):
    a, rd, dis = _validate(account), _readers(readers), []
    meta = rd["pr_meta"](a["pr"], a["repo"])
    fc = {"sha": meta["head"], "source": "GitHub PR"} if meta else {"sha": a["finalCommit"], "source": SESSION}
    ci, lane = _ci(rd, a["repo"], fc["sha"]), _lane(a, rd, meta)
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
    notes, missing = [], []
    for v in reviewers:
        if v["planned"] and v["ran"] == "not-run":
            mine = [g for g in a["goAheads"] if g["reviewer"] == v["name"]]
            good = next((g for g in mine if _go_ahead_ok(g)), None)
            if mine and not good:
                notes.append(f"the go-ahead for {v['name']} is incomplete")
            missing.append({"name": v["name"], "goAhead": good})
    unread = [str(p) for p in a["rawFindingsFiles"] if rd["read_text"](p) is None]
    # Identity is stamped on the unredacted account, so a later write compares the stored key.
    findings = [dict(f, **{session_contract.FINDING_KEY_FIELD: _key(f)}) for f in a["findings"]]
    walls = [v["observation"].get("wallSeconds") for v in reviewers if v["ran"] == "engine-record"
             and isinstance(v.get("observation"), dict)]
    toks = [v["observation"].get("tokens") for v in reviewers if v["ran"] == "engine-record"
            and isinstance(v.get("observation"), dict)]
    toks = [t for t in toks if isinstance(t, int) and not isinstance(t, bool)]
    ran_names = [v["name"] for v in reviewers if v["ran"] != "not-run"]
    rec = {
        "schema": RECORD_SCHEMA, "pr": a["pr"], "sessionId": a["sessionId"], "lane": lane, "makers": a["makers"],
        "laneBasis": _lane_basis(a, rd, lane["value"], fc["sha"]), "finalCommit": fc,
        "ci": ci, "reviewers": reviewers, "findings": findings, "unreadFiles": unread, "rawOutputs": [],
        "leftForOwner": [_name(f) for f in findings if f.get("outcome") == _LEFT_FOR_OWNER],
        "missingReviews": missing, "rounds": dict(a["rounds"], source=SESSION),
        "cost": {"unit": "reviewer-minutes",
                 "minutes": round(sum(w for w in walls if isinstance(w, (int, float))) / 60, 1),
                 "tokens": sum(toks) if toks else None, "source": "engine records",
                 "notCounted": [v["name"] for v in reviewers if v["ran"] != "engine-record"]},
        "sessionDisagreements": dis,
        "checked": [f"CI on {(fc['sha'] or 'unknown')[:7]}: {ci['state']}",
                    "Reviewers that ran: " + (", ".join(ran_names) or "none")] + a["checked"],
        "previousRecord": None,
        "writtenAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    rec["status"], rec["parked"], lines = _status(
        rec, [f"the raw output file {n} could not be read" for n in unread], _finding_lines(findings))
    rec["whatIsMissing"] = notes + lines
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


def render(record):
    record = _scrubbed(record)
    r, lane, ci = record, record["lane"], record["ci"]
    who = []
    for v in r["reviewers"]:
        label = {"engine-record": "ran (engine record)", "reported-by-session": f"ran ({SESSION})"}.get(
            v["ran"], "did not run")
        if v["ran"] != "not-run" and v.get("commit") and v["commit"] != r["finalCommit"]["sha"]:
            label += f" on {v['commit'][:7]}"
        word = v.get("ownerWord")
        who.append(f"- {v['name']}: {label}"
                   + ("; not independent of the makers" if v.get("notIndependent") else "")
                   + (f" (owner's word: {word['where']})" if v.get("notIndependent") and isinstance(word, dict)
                      and isinstance(word.get("where"), str) and word["where"] else "")
                   + f"; findings: {v['findingsCoverage']}")
    waits = []
    if r["leftForOwner"]:
        waits.append("findings left for the owner (" + ", ".join(r["leftForOwner"]) + ") wait for the owner's decision")
    if r["parked"]:
        waits.append("a review with no go-ahead is parked until the owner decides")
    waits_text = ("Waiting for the owner: " + "; ".join(waits) + ".") if waits else "Nothing waits for the owner."

    def compose(r):
        floor_line = (f"Risk floor: {r['laneBasis']['floor'] or 'none'} — " + "; ".join(r["laneBasis"]["why"]) + ".")
        lines = [
            f"**Review record: {r['status'].replace('-', ' ')}.** Checked: " + "; ".join(r["checked"][:2])
            + ". Left: " + ("; ".join(r["whatIsMissing"]) or "nothing") + ".",
            waits_text,
            f"Lane: {lane['value']} ({lane['source']})" + (f", because {lane['reason']}" if lane.get("reason") else "")
            + (f" ({lane['reasonSource']})" if lane.get("reason") and lane.get("reasonSource") else "") + ".",
            floor_line,
            *(["Makers: " + ", ".join(m["family"] for m in r["makers"]) + "."] if r["makers"] else []),
            f"CI on the final commit {(r['finalCommit']['sha'] or 'unknown')[:7]}: {ci['state']} ({ci['source']}).",
            "Reviewers:", *who,
            # axis: the shed line is present whenever a reviewer step ran — see bite-proof record wo_d_1795_reviewer-shed
            *([_reviewer_shed_line(r)] if r.get("reviewerShed") else [])]
        summary = "\n".join(lines)
        # The Risk floor line is the one place the lane basis's literal data (area names, sampled changed paths)
        # appears, so it alone is left out of the claim check (the line itself, never a string match), as the JSON
        # block is. Every other line is still checked.
        _assert_no_bug_free_claim("\n".join(l for l in lines if l is not floor_line))
        return (f"{MARKER}\n{summary}\n\n<details><summary>Full record</summary>\n\n```json\n"
                f"{json.dumps(r, indent=2, sort_keys=True)}\n```\n</details>")

    # The size bound is on what is posted (the JSON-escaped body), so it is measured here: shed the lane
    # basis's path evidence in a fixed order until the body fits. The floor, lane and proposalTaken never change.
    body = compose(r)
    for step in _SHED_STEPS:
        if len(body) <= MAX_BODY_CHARS:
            break
        r = dict(r, laneBasis=step(r["laneBasis"]))
        body = compose(r)
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
        body = compose(r)
    # axis: a body still over the cap after every step is refused, never truncated — see bite-proof record wo_d_1795_reviewer-shed
    if len(body) > MAX_BODY_CHARS:
        raise Refusal("review-record-too-large", f"{len(body)} characters")
    return body


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


def _parse_body(body):
    try:
        rec = json.loads(body[body.index("```json\n") + 8:body.rindex("\n```\n</details>")])
    except ValueError:
        return None
    return rec if isinstance(rec, dict) and rec.get("schema") == RECORD_SCHEMA else None


def _marker_comments(rd, pr, repo):
    """The record comments on the PR, oldest first (comment ids only grow)."""
    comments = rd["list_comments"](pr, repo)
    if comments is None:
        raise Refusal("review-record-gh-failed", "the PR comments could not be listed")
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
        found = _marker_comments(rd, pr, repo)
        latest = found[-1] if found else None
        prior = None
        if latest:
            prior = _parse_body(latest["body"])
            if prior is None:
                raise Refusal("review-record-unreadable", latest.get("url") or "the existing record")
        missing = _unaccounted(prior, a["findings"])
        if missing:
            raise Refusal("review-record-unaccounted",
                          "earlier findings with no outcome in this account: " + ", ".join(missing))
        record = build_record(a, rd)
        raws = [(os.path.basename(p), *render_raw(os.path.basename(p), read_text(p)))
                for p in a["rawFindingsFiles"] if str(p) not in record["unreadFiles"]]
        previous = {"id": latest["id"], "url": latest.get("url")} if latest else None
        # Refuse here, before any comment is created, if the record cannot be posted.
        render(dict(record, previousRecord=previous and {"id": 10 ** 15, "url": "u" * 120},
                    rawOutputs=[{"file": n, "id": 10 ** 15, "url": "u" * 120, "withheld": w} for n, _, w in raws]))
        links = []
        for name, body, withheld in raws:
            sent = rd["create_comment"](pr, repo, body)
            if sent is None:
                raise Refusal("review-record-gh-failed", f"the raw output comment for {name} could not be written")
            links.append({"file": name, "id": sent["id"], "url": sent.get("url"), "withheld": withheld})
        record.update(rawOutputs=links, previousRecord=previous)
        sent = rd["create_comment"](pr, repo, render(record))
        if sent is None:
            raise Refusal("review-record-gh-failed", "the record comment could not be written")
        return {"ok": True, "action": "created", "url": sent.get("url"),
                "status": record["status"], "parked": record["parked"], "whatIsMissing": record["whatIsMissing"]}
    return _guarded(go)


def read(pr, repo=None, readers=None):
    def go():
        rd = _readers(readers)
        found = _marker_comments(rd, pr, repo)
        if not found:
            raise Refusal("review-record-missing", f"no review record on PR {pr}")
        latest = found[-1]
        rec = _parse_body(latest["body"])
        if rec is None:
            raise Refusal("review-record-unreadable", latest.get("url") or "the existing record")
        return {"ok": True, "url": latest.get("url"), **rec, "earlierRecords": [c.get("url") for c in found[:-1]]}
    return _guarded(go)


def _shows_reading(run):
    obs = run.get("observation") if isinstance(run, dict) else None
    # the record writer credits a run only when it is a graded review: hold the reading to the same rule
    return (isinstance(run, dict) and run.get("graded") is True
            and run.get("runKind") == session_contract.RUN_KIND_REVIEW
            and isinstance(obs, dict) and obs.get("read") == "engaged")


def _move_up_blocker(seat_map, maker_families):
    """The first reason a seat map does not let a second no-reading review move up to the full lane, else None."""
    roster = seat_map.get("roster") if isinstance(seat_map, dict) else None
    if not isinstance(roster, list) or not roster:
        return "the seat map has no roster"
    # axis: a map composed for fewer seats than the full panel cannot show the whole panel independent, so it parks
    if not set(seat_map_module.PANEL_ROSTER) <= set(roster):
        return "the seat map's roster omits a panel seat"
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


def reading_next(runs, seat_map, maker_families):
    """What follows a review whose reading is not shown: accept, rerun, move-up or park. Pure: no model call, no write."""
    runs = list(runs)[:2]
    if any(_shows_reading(run) for run in runs):
        return {"next": "accept", "reason": "the engine's record shows that the reviewer read the change"}
    if not runs:
        return {"next": "park", "reason": "no run was given, so no reading can be shown"}
    if len(runs) < 2:
        return {"next": "rerun", "reason": "the one run does not show that the reviewer read the change"}
    blocker = _move_up_blocker(seat_map, frozenset(maker_families))
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
