#!/usr/bin/env python3
"""The review record: one marker-tagged PR comment per PR, decided in one place.

build_record() is the only place a status, a reviewer's ran-state or a code fact is decided;
write() and read() do I/O only. Facts that code holds (lane, final commit, CI, whether a
reviewer with a run directory ran) come from code, never from the session's account.

CLI:
  review_record.py write --account FILE --repo-root DIR
  review_record.py read --pr N [--repo OWNER/NAME]
"""
from __future__ import annotations

import argparse
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
import model_registry  # noqa: E402
import pr_comment  # noqa: E402
import review_findings_schema as rfs  # noqa: E402
import session_contract  # noqa: E402
import store_core  # noqa: E402

MARKER = "<!-- superheroes:review-record -->"
ARCHIVE_MARKER = "<!-- superheroes:review-record-archive -->"
ARCHIVE_SCHEMA = "review-record-archive/1"
ACCOUNT_SCHEMA = "review-account/1"
RECORD_SCHEMA = "review-record/1"
FORBIDDEN_CLAIMS = ("no bugs", "bug-free", "bug free")
MAX_BODY_CHARS = 65000
SESSION = "reported by the session"
_LEFT_FOR_OWNER = rfs.LEFT_FOR_OWNER
_RED = frozenset({"failure", "timed_out", "cancelled", "action_required", "startup_failure", "stale"})
_LANE_RE = re.compile(r"(?m)^\*\*Lane call:\*\*\s*(full|light|micro)\b[.:]?[ \t]*(.*)$")
_VENDOR_MODELS = {"claude": model_registry.claude_models, "codex": model_registry.codex_models,
                  "cursor": model_registry.cursor_models}


class Refusal(Exception):
    def __init__(self, reason, detail):
        super().__init__(reason, detail)
        self.reason, self.detail = reason, detail


def _refuse(reason, detail):
    return {"ok": False, "reason": reason, "detail": detail}


# --- default readers: each wraps a tool and never raises; an error becomes None ---

def _run(argv):
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=60)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def _gh_json(*args):
    out = _run(["gh", *args])
    try:
        return None if out is None else json.loads(out)
    except ValueError:
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


def _edit_comment(cid, repo, body):
    return _send("PATCH", _api(repo, f"issues/comments/{cid}"), body)


def _readers(overrides):
    return {"pr_meta": _pr_meta, "issue_body": _issue_body, "check_data": _check_data,
            "lane_marker": _lane_marker, "engine_run": _engine_run, "list_comments": _list_comments,
            "create_comment": _create_comment, "edit_comment": _edit_comment, **(overrides or {})}


# --- the account ---

def _validate(a):
    def chk(ok, key):
        if not ok:
            raise Refusal("review-account-invalid", key)
    ne = lambda v: isinstance(v, str) and bool(v)  # noqa: E731
    sn = lambda v: v is None or isinstance(v, str)  # noqa: E731
    lst = lambda k: a.get(k, []) if isinstance(a.get(k, []), list) else chk(False, k)  # noqa: E731
    chk(isinstance(a, dict), "account")
    chk(a.get("schema") == ACCOUNT_SCHEMA, "schema")
    pr = a.get("pr")
    chk(isinstance(pr, int) and not isinstance(pr, bool) and pr > 0, "pr")
    chk(a.get("repo") is None or (isinstance(a["repo"], str) and re.fullmatch(r"[^/\s]+/[^/\s]+", a["repo"])), "repo")
    chk(ne(a.get("sessionId")), "sessionId")
    for k in ("lane", "laneReason", "finalCommit", "ci"):
        chk(sn(a.get(k)), k)
    for i, m in enumerate(lst("makers")):
        chk(isinstance(m, dict) and ne(m.get("family")), f"makers[{i}]")
    chk(isinstance(a.get("reviewers"), list) and a["reviewers"], "reviewers")
    for i, r in enumerate(a["reviewers"]):
        chk(isinstance(r, dict), f"reviewers[{i}]")
        for k in ("name", "vendor", "model"):
            chk(ne(r.get(k)), f"reviewers[{i}].{k}")
        for k in ("planned", "ran"):
            chk(isinstance(r.get(k), bool), f"reviewers[{i}].{k}")
        chk(sn(r.get("runDir")), f"reviewers[{i}].runDir")
        chk(r.get("ownerWord") is None or isinstance(r["ownerWord"], dict), f"reviewers[{i}].ownerWord")
    for i, f in enumerate(lst("findings")):
        chk(isinstance(f, dict) and ne(f.get("id")), f"findings[{i}].id")
        chk(f.get("outcome") is None or f["outcome"] in rfs.OUTCOMES,
            f"findings[{i}].outcome (allowed: {', '.join(rfs.OUTCOMES)}; or null while undecided)")
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
    return {"repo": None, "lane": None, "laneReason": None, "finalCommit": None, "ci": None, "makers": [],
            "findings": [], "rawFindingsFiles": [], "goAheads": [], "checked": [], **a, "rounds": rounds}


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


def _lane(a, rd, meta):
    m = rd["lane_marker"](a.get("repoRoot"))
    if isinstance(m, dict) and m.get("schema") == build_lane.BUILD_LANE_SCHEMA and m.get("lane") == "full" \
            and m.get("branch") == m.get("currentBranch"):
        return {"value": "full", "source": "build lane marker", "reason": None}
    if meta:
        texts = [(rd["issue_body"](n, a["repo"]), "issue lane call") for n in meta["issues"]]
        for body, source in texts + [(meta["body"], "PR lane call")]:
            hit = _LANE_RE.search(body or "")
            if hit:
                return {"value": hit.group(1), "source": source, "reason": hit.group(2).strip() or None}
    return {"value": a["lane"], "source": SESSION, "reason": a["laneReason"]}


def _family(vendor, model):
    fam = model_registry.model_family(vendor, model)
    if fam or vendor not in _VENDOR_MODELS:
        return fam
    shared = {model_registry.model_family(vendor, m) for m in _VENDOR_MODELS[vendor]()}
    return shared.pop() if len(shared) == 1 else None


def _owner_word_ok(w):
    return isinstance(w, dict) and bool(w.get("words")) and bool(w.get("where"))


def _go_ahead_ok(g):
    if g.get("kind") == "standing-ruling":
        return bool(g.get("canonId"))
    return bool(g.get("words")) and bool(g.get("where"))


def _go_text(g):
    return f"standing ruling {g['canonId']}" if g["kind"] == "standing-ruling" else f"owner's words ({g['where']})"


def _short(sha):
    return (sha or "")[:7] or "unknown"


def _reviewer(r, makers, rd, dis, head=None):
    out = {k: r.get(k) for k in ("name", "vendor", "model", "planned", "runDir")}
    out["family"] = _family(r["vendor"], r["model"])
    # The runner's record does not expose a findings run's content: the code holds no reviewer's findings.
    out["findingsCoverage"] = "reported by the session"
    if r.get("runDir"):
        rec, err = rd["engine_run"](r["runDir"])
        if isinstance(rec, dict) and rec.get("runKind") == "review" \
                and rec.get("resultKind") and rec.get("resultDigest") and rec.get("graded") is True:
            seen = rec.get("viewHeadSha")
            if not head or seen != head:
                # A review of another commit (or of an unknown one) never covers the final commit.
                out.update(ran="not-run", runNote=f"the review covered {_short(seen)}, not the final commit "
                                                  f"{_short(head)}" if seen else "the commit the review covered is unknown")
                if r["ran"]:
                    dis.append({"fact": f"{r['name']} ran on the final commit", "session": True, "code": "not-run"})
            else:
                out.update(ran="engine-record", observation=rec.get("observation"))
            source, model = rec.get("source"), rec.get("engineModel") or rec.get("model")
            if isinstance(source, str) and source:
                # The run's own engine and model decide the family; the account's claim is only a claim.
                run_family = _family(source, model) if isinstance(model, str) and model else None
                if run_family != out["family"]:
                    dis.append({"fact": f"{r['name']} family", "session": out["family"], "code": run_family})
                    out["family"] = run_family
        else:
            out.update(ran="not-run", runNote=err or "no review result")
            if r["ran"]:
                dis.append({"fact": f"{r['name']} ran", "session": True, "code": "not-run"})
    else:
        out["ran"] = "reported-by-session" if r["ran"] else "not-run"
    if not makers:
        out["independent"], out["independenceNote"] = None, "makers not recorded"
    else:
        out["independent"] = None if out["family"] is None else out["family"] not in {m["family"] for m in makers}
    if out["ran"] != "not-run" and makers and out["independent"] is not True:
        if _owner_word_ok(r.get("ownerWord")):
            out.update(notIndependent=True, ownerWord=r["ownerWord"])
        else:
            out.update(ran="not-run", runNote="not shown independent of the makers")
    return out


_SETTLES_OWNER = tuple(o for o in rfs.OUTCOMES if o not in (_LEFT_FOR_OWNER, "craft"))


def _raw_rows(members, source):
    """The whole reviewer member (every canonical key it carries) plus where it came from."""
    return [{**{k: m[k] for k in rfs.CANONICAL_MEMBER_KEYS if k in m}, "sourceFile": source}
            for m in members if isinstance(m, dict)]


def _raw_findings(paths):
    raw, unread, read = [], [], []
    for p in paths:
        try:
            with open(p, encoding="utf-8") as fh:
                members = json.load(fh)
            if isinstance(members, dict):
                members = members["findings"]
            assert isinstance(members, list) and all(isinstance(m, dict) for m in members)
        except (OSError, ValueError, KeyError, TypeError, AssertionError):
            unread.append(os.path.basename(p))
            continue
        read.append(os.path.basename(p))
        raw += _raw_rows(members, os.path.basename(p))
    return raw, unread, read


def _key(f):
    return session_contract.finding_identity_key(f)


def _decided(f, settles=rfs.OUTCOMES):
    return f.get("outcome") in settles and bool(f.get("reason"))


def _name(f):
    return f.get("id") or f"at {f.get('file')}:{f.get('line')}"


def _ref(f):
    """An owed entry for a finding the record already holds in full: its identity and what names it."""
    keep = ("id", "title", "file", "line", "outcome", "reason", "sourceFile")
    return {**{k: f[k] for k in keep if k in f}, session_contract.FINDING_KEY_FIELD: _key(f)}


def _owed(findings, raw, prior):
    """One check, by finding identity (session_contract.finding_identity_key), never by id.

    Every finding the prior record held (its findings and its owed list) must reappear in this
    account with one of the outcomes and a reason; every reviewer finding must match an account
    finding that has both. Anything else is owed. Nothing is cleared by omission.
    """
    by_key, owed, lines = {}, {}, []
    for f in findings:
        by_key.setdefault(_key(f), []).append(f)
        if f.get("outcome") not in rfs.OUTCOMES:
            lines.append(f"finding {_name(f)} has no outcome")
        elif not f.get("reason"):
            lines.append(f"finding {_name(f)} has no reason")
        elif f["outcome"] == _LEFT_FOR_OWNER:
            lines.append(f"finding {_name(f)} waits for the owner's decision")
    earlier = {}
    for p in list((prior or {}).get("findings") or []) + list((prior or {}).get("owed") or []):
        if isinstance(p, dict):
            # The fullest copy (the findings list) is kept; any copy still left for the owner keeps it so.
            kept = earlier.setdefault(_key(p), dict(p))
            if p.get("outcome") == _LEFT_FOR_OWNER:
                kept["outcome"] = _LEFT_FOR_OWNER
                kept["reason"] = kept.get("reason") or p.get("reason")
    for k, p in earlier.items():
        mine = by_key.get(k, [])
        settles = _SETTLES_OWNER if p.get("outcome") == _LEFT_FOR_OWNER else rfs.OUTCOMES
        if any(_decided(f, settles) and f["outcome"] != _LEFT_FOR_OWNER for f in mine):
            continue
        if any(f.get("outcome") == _LEFT_FOR_OWNER and f.get("reason") for f in mine):
            continue  # still left for the owner: owed below, from this account's copy
        # Held in full only when this account no longer holds it; otherwise a reference.
        owed.setdefault(k, dict(p) if not mine else _ref(p))
        if not mine:
            lines.append(f"finding {_name(p)} from the earlier record is not in this account, so it is still owed"
                         + ("; it waits for the owner's decision" if p.get("outcome") == _LEFT_FOR_OWNER else ""))
        elif any(_decided(f) and f["outcome"] != _LEFT_FOR_OWNER for f in mine):
            lines.append(f"finding {_name(p)} was left for the owner; only "
                         + ", ".join(_SETTLES_OWNER) + " settles it")
    for f in findings:
        if not _decided(f) or f["outcome"] == _LEFT_FOR_OWNER:
            owed.setdefault(_key(f), _ref(f))
    for r in raw:
        if not any(_decided(f) for f in by_key.get(_key(r), [])):
            # Whole: the raw file may be gone on a later write, and this is then the only copy of its text.
            mine = by_key.get(_key(r), [{}])[0]
            owed.setdefault(_key(r), {**r, **{k: mine[k] for k in ("outcome", "reason") if k in mine},
                                      session_contract.FINDING_KEY_FIELD: _key(r)})
            lines.append(f"reviewer finding {_name(r)} in {r.get('sourceFile')} has no recorded outcome")
    return list(owed.values()), lines


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
    for m in rec["missingReviews"]:
        lines.append(f"{m['name']} did not run" + (f"; go-ahead: {_go_text(m['goAhead'])}" if m["goAhead"] else ""))
    if not any(v["planned"] and v["ran"] != "not-run" for v in rec["reviewers"]):
        lines.append("no planned reviewer ran")
    if not rec["makers"]:
        lines.append("the makers' model families were not recorded")
    return ("not-reviewed" if lines else "reviewed"), any(m["goAhead"] is None for m in rec["missingReviews"]), lines


def build_record(account, readers, prior=None):
    a, rd, dis = _validate(account), _readers(readers), []
    meta = rd["pr_meta"](a["pr"], a["repo"])
    fc = {"sha": meta["head"], "source": "GitHub PR"} if meta else {"sha": a["finalCommit"], "source": SESSION}
    ci, lane = _ci(rd, a["repo"], fc["sha"]), _lane(a, rd, meta)
    for fact, session, code, from_code in (("lane", a["lane"], lane["value"], lane["source"] != SESSION),
                                           ("finalCommit", a["finalCommit"], fc["sha"], bool(meta)),
                                           ("ci", a["ci"], ci["state"], ci["source"] == "GitHub checks")):
        if from_code and session is not None and session != code:
            dis.append({"fact": fact, "session": session, "code": code})
    reviewers = [_reviewer(r, a["makers"], rd, dis, fc["sha"]) for r in a["reviewers"]]
    notes, missing = [], []
    for v in reviewers:
        if v["planned"] and v["ran"] == "not-run":
            mine = [g for g in a["goAheads"] if g["reviewer"] == v["name"]]
            good = next((g for g in mine if _go_ahead_ok(g)), None)
            if mine and not good:
                notes.append(f"the go-ahead for {v['name']} is incomplete")
            missing.append({"name": v["name"], "goAhead": good})
    raw, unread, read = _raw_findings(a["rawFindingsFiles"])
    # An unread file stays owed across rewrites until a later account supplies that file readably.
    prior_unread = (prior or {}).get("unreadFiles")
    unread = list(dict.fromkeys(unread + [n for n in (prior_unread if isinstance(prior_unread, list) else [])
                                          if isinstance(n, str) and n not in read]))
    findings = [dict(f) for f in a["findings"]]
    walls = [v["observation"].get("wallSeconds") for v in reviewers if v["ran"] == "engine-record"
             and isinstance(v.get("observation"), dict)]
    toks = [v["observation"].get("tokens") for v in reviewers if v["ran"] == "engine-record"
            and isinstance(v.get("observation"), dict)]
    toks = [t for t in toks if isinstance(t, int) and not isinstance(t, bool)]
    ran_names = [v["name"] for v in reviewers if v["ran"] != "not-run"]
    hist = list((prior or {}).get("history") or [])
    if prior and prior.get("sessionId") != a["sessionId"]:
        hist.append({k: prior.get(k) for k in ("sessionId", "finalCommit", "findings", "rawFindings")})
    owed, finding_lines = _owed(findings, raw, prior)
    rec = {
        "schema": RECORD_SCHEMA, "pr": a["pr"], "sessionId": a["sessionId"], "lane": lane, "finalCommit": fc,
        "ci": ci, "makers": a["makers"], "reviewers": reviewers, "findings": findings, "rawFindings": raw, "unreadFiles": unread,
        "owed": owed, "leftForOwner": [_name(f) for f in owed if f.get("outcome") == _LEFT_FOR_OWNER],
        "historyArchives": list((prior or {}).get("historyArchives") or []),
        "missingReviews": missing, "rounds": dict(a["rounds"], source=SESSION),
        "cost": {"unit": "reviewer-minutes",
                 "minutes": round(sum(w for w in walls if isinstance(w, (int, float))) / 60, 1),
                 "tokens": sum(toks) if toks else None, "source": "engine records",
                 "notCounted": [v["name"] for v in reviewers if v["ran"] != "engine-record"]},
        "sessionDisagreements": dis,
        "checked": [f"CI on {(fc['sha'] or 'unknown')[:7]}: {ci['state']}",
                    "Reviewers that ran: " + (", ".join(ran_names) or "none")] + a["checked"],
        "history": [h for h in hist if h.get("sessionId") != a["sessionId"]],
        "writtenAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    rec["status"], rec["parked"], lines = _status(
        rec, [f"the findings file {n} could not be read" for n in unread], finding_lines)
    rec["whatIsMissing"] = notes + lines
    return rec


# --- render, write, read ---

def _assert_no_bug_free_claim(text):
    low = text.lower()
    for phrase in FORBIDDEN_CLAIMS:
        if phrase in low:
            raise Refusal("review-record-forbidden-claim", phrase)


def _scrubbed(value):
    if isinstance(value, str):
        return pr_comment.scrub(value)
    if isinstance(value, list):
        return [_scrubbed(v) for v in value]
    if isinstance(value, dict):
        return {k: _scrubbed(v) for k, v in value.items()}
    return value


def render(record):
    record = _scrubbed(record)
    r, lane, ci = record, record["lane"], record["ci"]
    who = []
    for v in r["reviewers"]:
        label = {"engine-record": "ran (engine record)", "reported-by-session": f"ran ({SESSION})"}.get(
            v["ran"], "did not run")
        note = "; same family as a maker, owner's word on record" if v.get("notIndependent") else ""
        who.append(f"- {v['name']}: {label}{note}; findings: {v['findingsCoverage']}")
    waits = []
    if r["leftForOwner"]:
        waits.append("findings left for the owner (" + ", ".join(r["leftForOwner"]) + ") wait for the owner's decision")
    if r["parked"]:
        waits.append("a review with no go-ahead is parked until the owner decides")
    summary = "\n".join([
        f"**Review record: {r['status'].replace('-', ' ')}.** Checked: " + "; ".join(r["checked"][:2])
        + ". Left: " + ("; ".join(r["whatIsMissing"]) or "nothing") + ".",
        ("Waiting for the owner: " + "; ".join(waits) + ".") if waits else "Nothing waits for the owner.",
        f"Lane: {lane['value']} ({lane['source']})" + (f", because {lane['reason']}" if lane.get("reason") else "") + ".",
        f"CI on the final commit {(r['finalCommit']['sha'] or 'unknown')[:7]}: {ci['state']} ({ci['source']}).",
        "Reviewers:", *who])
    _assert_no_bug_free_claim(summary)
    body = (f"{MARKER}\n{summary}\n\n<details><summary>Full record</summary>\n\n```json\n"
            f"{json.dumps(r, indent=2, sort_keys=True)}\n```\n</details>")
    if len(body) > MAX_BODY_CHARS:
        raise Refusal("review-record-too-large", f"{len(body)} characters")
    return body


def render_archive(entries):
    """An archive comment: one earlier session's complete entry, verbatim, serialized compactly.

    Compact (no indent) so an archive is never larger than the record body it came out of.
    """
    payload = _scrubbed({"schema": ARCHIVE_SCHEMA, "history": entries})
    intro = ("Earlier sessions of this PR's review record, kept in full. "
             "The review record comment names this comment.")
    # Only the sentence this writer authors is checked: the entries are reviewers' verbatim text.
    _assert_no_bug_free_claim(intro)
    body = (f"{ARCHIVE_MARKER}\n{intro}\n\n<details><summary>Earlier sessions</summary>\n\n```json\n"
            f"{json.dumps(payload, separators=(',', ':'), sort_keys=True)}\n```\n</details>")
    if len(body) > MAX_BODY_CHARS:
        raise Refusal("review-record-too-large", f"an earlier session alone is {len(body)} characters")
    return body


def _parse_body(body, schema=RECORD_SCHEMA):
    try:
        rec = json.loads(body[body.index("```json\n") + 8:body.rindex("\n```\n</details>")])
    except ValueError:
        return None
    return rec if isinstance(rec, dict) and rec.get("schema") == schema else None


def _marker_comments(rd, pr, repo):
    comments = rd["list_comments"](pr, repo)
    if comments is None:
        raise Refusal("review-record-gh-failed", "the PR comments could not be listed")
    found = [c for c in comments if str(c.get("body", "")).startswith(MARKER)]
    if len(found) > 1:
        raise Refusal("review-record-duplicate", f"{len(found)} review-record comments on PR {pr}")
    return found


def _guarded(fn):
    try:
        return fn()
    except Refusal as e:
        return _refuse(e.reason, e.detail)
    except Exception as e:  # nothing raises to the caller
        return _refuse("review-record-internal-error", f"{type(e).__name__}: {e}")


def _load_archives(rd, pr, repo, rec):
    """The earlier sessions a record's archive comments hold; refuses if any is missing or unreadable."""
    archived = []
    if rec.get("historyArchives"):
        wanted = {x.get("id") for x in rec["historyArchives"] if isinstance(x, dict)}
        comments = rd["list_comments"](pr, repo)
        if comments is None:
            raise Refusal("review-record-unreadable", "the archive comments could not be fetched")
        seen = set()
        for c in comments:
            if c.get("id") in wanted and str(c.get("body", "")).startswith(ARCHIVE_MARKER):
                parsed = _parse_body(c["body"], ARCHIVE_SCHEMA)
                if parsed is None:
                    raise Refusal("review-record-unreadable", c.get("url") or "an archive comment")
                seen.add(c.get("id"))
                archived += parsed.get("history") or []
        if wanted - seen:
            raise Refusal("review-record-unreadable", "a referenced archive comment is missing")
    return archived


def write(account_path, repo_root, readers=None):
    def go():
        try:
            with open(account_path, encoding="utf-8") as fh:
                account = json.load(fh)
        except (OSError, ValueError):
            raise Refusal("review-account-invalid", "account file")
        account = dict(account, repoRoot=repo_root) if isinstance(account, dict) else account
        rd = _readers(readers)
        _validate(account)
        found = _marker_comments(rd, account["pr"], account.get("repo"))
        prior = None
        if found:
            prior = _parse_body(found[0]["body"])
            if prior is None:
                raise Refusal("review-record-unreadable", found[0].get("url") or "the existing record")
            _load_archives(rd, account["pr"], account.get("repo"), prior)  # refuse before editing if history is lost
        record = build_record(account, rd, prior)
        try:
            body = render(record)
        except Refusal as e:
            if e.reason != "review-record-too-large" or not record["history"]:
                raise
            # Nothing is trimmed: each full earlier session moves to its own comment on the PR,
            # and the record names them. All are rendered first (a session that cannot fit refuses
            # before anything is written), and the archives are written before the record.
            bodies = [render_archive([h]) for h in record["history"]]
            made = []
            for h, text in zip(record["history"], bodies):
                archive = rd["create_comment"](account["pr"], account.get("repo"), text)
                if archive is None:
                    raise Refusal("review-record-gh-failed", "the archive comment could not be written")
                made.append({"id": archive["id"], "url": archive.get("url"), "sessionIds": [h.get("sessionId")]})
            record = dict(record, history=[], historyArchives=record["historyArchives"] + made)
            body = render(record)
        sent = (rd["edit_comment"](found[0]["id"], account.get("repo"), body) if found
                else rd["create_comment"](account["pr"], account.get("repo"), body))
        if sent is None:
            raise Refusal("review-record-gh-failed", "the record comment could not be written")
        return {"ok": True, "action": "edited" if found else "created", "url": sent.get("url"),
                "status": record["status"], "parked": record["parked"], "whatIsMissing": record["whatIsMissing"]}
    return _guarded(go)


def read(pr, repo=None, readers=None):
    def go():
        rd = _readers(readers)
        found = _marker_comments(rd, pr, repo)
        if not found:
            raise Refusal("review-record-missing", f"no review record on PR {pr}")
        rec = _parse_body(found[0]["body"])
        if rec is None:
            raise Refusal("review-record-unreadable", found[0].get("url") or "the existing record")
        archived = _load_archives(rd, pr, repo, rec)
        return {"ok": True, "url": found[0].get("url"), **rec, "archivedHistory": archived}
    return _guarded(go)


def main(argv=None):
    parser = argparse.ArgumentParser(prog="review_record")
    sub = parser.add_subparsers(dest="command", required=True)
    w = sub.add_parser("write")
    w.add_argument("--account", required=True)
    w.add_argument("--repo-root", required=True, dest="repo_root")
    r = sub.add_parser("read")
    r.add_argument("--pr", type=int, required=True)
    r.add_argument("--repo", default=None)
    args = parser.parse_args(argv)
    result = write(args.account, args.repo_root) if args.command == "write" else read(args.pr, args.repo)
    print(json.dumps(result))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
