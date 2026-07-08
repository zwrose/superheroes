# plugins/superheroes/lib/pr_body.py
"""Pure PR-body composition for the ship-phase honesty gates (issue #228).

Two generated sections are seeded into the draft PR's body so the build/ship legs FILL
them rather than invent them:

  - the **Definition of done** disposition table (skeleton: one blank row per spec DoD
    bullet), anchored on `dod_gate.TABLE_MARKER`; the mark-ready DoD gate reads it back.
  - the generated **Stubbed seams** section (one line per `STUB(#NNN)` marker in the PR
    diff), anchored on `STUBS_MARKER`. Generated, not authored, so it cannot be omitted;
    an empty section is omitted entirely (no noise on stub-free PRs).

Composition is idempotent: a body that already carries a section's marker is left as-is
(so re-seeding on resume never double-appends)."""
import dod_gate

STUBS_MARKER = "superheroes:stubbed-seams"


def seed_dod_block(dod_bullets):
    """The DoD disposition-table skeleton (blank Disposition/Evidence per bullet), or "" when
    there are no bullets to seed."""
    if not dod_bullets:
        return ""
    lines = [
        "## Definition of done",
        "",
        "<!-- %s — one row per spec Definition-of-done bullet. Set Disposition to `done`"
        % dod_gate.TABLE_MARKER,
        "     (+ evidence: test name / quoted record / link) or `deferred` (+ a filed issue",
        "     `#NNN` and a one-line reason). mark-ready parks the run on any unaddressed bullet. -->",
        "",
        "| DoD bullet | Disposition | Evidence / deferral |",
        "| --- | --- | --- |",
    ]
    for b in dod_bullets:
        lines.append("| %s |  |  |" % dod_gate.cellsafe(b))
    return "\n".join(lines) + "\n"


def stubbed_seams_block(markers):
    """The generated "Stubbed seams" section from diff markers (see stub_markers.markers_in_diff),
    or "" when there are none (the section is omitted entirely on a stub-free PR)."""
    if not markers:
        return ""
    lines = [
        "## Stubbed seams",
        "",
        "<!-- %s — generated from STUB(#NNN) markers in this PR's diff. Do not edit by hand. -->"
        % STUBS_MARKER,
        "",
    ]
    for m in markers:
        desc = str(m.get("description") or "").strip() or "(no description)"
        lines.append("- `%s` — %s (#%s)" % (m.get("file", "?"), desc, m.get("issue")))
    return "\n".join(lines) + "\n"


def compose_body(base_body, dod_block, stubs_block):
    """Append whichever generated blocks are non-empty and not already present (by marker) to
    `base_body`. Idempotent: re-seeding a body that already carries a block is a no-op for it."""
    base = (base_body or "").rstrip()
    parts = [base] if base else []
    if dod_block and dod_gate.TABLE_MARKER not in base:
        parts.append(dod_block.rstrip())
    if stubs_block and STUBS_MARKER not in base:
        parts.append(stubs_block.rstrip())
    if not parts:
        return ""
    return "\n\n".join(parts) + "\n"


# ---- #219: durable "what & why" PR-body composition (extends the #228 seeding module above) ----
import argparse
import json
import os
import subprocess
import sys

_DIFF_EXCERPT_CAP = 12000   # chars — keep the compose prompt bounded
_COMMIT_CAP = 25            # subjects
_INTENT_LINES = 60          # intent-doc body lines
_ISSUE_BODY_CAP = 2000      # chars of the linked issue body


def _git(args, cwd):
    try:
        r = subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd, timeout=30)
        return (r.returncode, (r.stdout or ""))
    except Exception:
        return (2, "")


def _resolve_base(worktree, base):
    import base_ref
    try:
        return base_ref.resolve_configured_base(worktree, base or "main")
    except Exception:
        return None


def _commits(worktree, base):
    if not base:
        return []
    rc, out = _git(["log", "--reverse", "--format=%s", "%s..HEAD" % base], worktree)
    subs = [ln for ln in out.splitlines() if ln.strip()] if rc == 0 else []
    return subs[:_COMMIT_CAP]


def _intent(work_item, root, cwd):
    """(issue, intent_excerpt) from the work-item's tasks (else spec) definition-doc. Fail-soft:
    a missing/unresolvable doc yields (None, '') so the diff still drives the body."""
    import definition_doc
    issue, excerpt = None, ""
    try:
        wdir = definition_doc.resolve_work_item_dir(work_item, root=root, cwd=cwd)
    except Exception:
        return (None, "")
    for doc in ("tasks", "spec"):
        path = os.path.join(wdir, "%s.md" % doc)
        if not os.path.exists(path):
            continue
        try:
            fm, body = definition_doc.read_frontmatter(path)
        except Exception:
            continue
        if issue is None:
            v = fm.get("issue")
            if v not in (None, "", "null"):
                issue = str(v)
        if not excerpt:
            excerpt = "\n".join(body.splitlines()[:_INTENT_LINES]).strip()
    return (issue, excerpt)


def _issue_meta(issue):
    if not issue:
        return (None, None)
    try:
        r = subprocess.run(["gh", "issue", "view", str(issue), "--json", "title,body"],
                           capture_output=True, text=True, timeout=20)
        if r.returncode == 0 and r.stdout.strip():
            d = json.loads(r.stdout)
            return (d.get("title"), (d.get("body") or "")[:_ISSUE_BODY_CAP])
    except Exception:
        pass
    return (None, None)


def _usable(text):
    return isinstance(text, str) and text.strip() != ""


def _prior_body_usable(body_path):
    """True when the durable composed-body file exists with non-blank content. This is the
    RESUME-REUSE probe — it lives here (Python, reads its own file) because the spine must never
    io()-read a maybe-missing file (proseReads == 0 invariant; rev-2 change)."""
    if not body_path:
        return False
    try:
        with open(body_path, encoding="utf-8") as fh:
            return _usable(fh.read())
    except OSError:
        return False


def split_prose(body):
    """(prose, generated_tail) — the tail starts at the earliest #228 generated section (the
    '## ' heading whose section carries dod_gate.TABLE_MARKER or STUBS_MARKER). #219 owns only
    the prose; callers re-attach the tail unchanged so a filled DoD table is never lost."""
    text = body or ""
    cut = len(text)
    for marker in (dod_gate.TABLE_MARKER, STUBS_MARKER):
        i = text.find(marker)
        if i < 0:
            continue
        h = text.rfind("\n## ", 0, i)
        start = (h + 1) if h >= 0 else (0 if text.startswith("## ") else i)
        cut = min(cut, start)
    return (text[:cut].rstrip(), text[cut:] if cut < len(text) else "")


def gather_context(work_item, worktree, root, base, issue_override=None, body_path=None):
    base_sha = _resolve_base(worktree, base)
    commits = _commits(worktree, base_sha)
    diffstat = diff_excerpt = ""
    if base_sha:
        _, diffstat = _git(["diff", "--stat", "%s...HEAD" % base_sha], worktree)
        _, diff_full = _git(["diff", "%s...HEAD" % base_sha], worktree)
        diff_excerpt = diff_full[:_DIFF_EXCERPT_CAP]
    issue, intent = _intent(work_item, root, worktree)
    if issue_override:
        issue = str(issue_override)
    issue_title, issue_body = _issue_meta(issue)
    return {
        "work_item": work_item,
        "issue": issue,
        "issue_title": issue_title,
        "issue_body": issue_body,
        "commits": commits,
        "diffstat": diffstat.strip(),
        "diff_excerpt": diff_excerpt,
        "intent_excerpt": intent,
        "prior_body_usable": _prior_body_usable(body_path),
    }


def _cmd_context(a):
    print(json.dumps(gather_context(a.work_item, a.worktree or os.getcwd(),
                                    a.root or os.getcwd(), a.base, a.issue, a.body_path)))


def _ensure_closes(body, issue):
    if issue and ("Closes #%s" % issue) not in body:
        body = body.rstrip() + "\n\nCloses #%s" % issue
    return body


def fallback_body(work_item, issue, commits):
    """A DETERMINISTIC, real body from local data only (no Sonnet, no network) — the floor when
    the smart compose is unavailable (owner Decision 2). Lean what & why + Closes #N."""
    commits = commits or []
    lead = (commits[0] if commits else "Changes for %s" % work_item).strip()
    lines = [lead, "", "## What changed"]
    lines += (["- %s" % c for c in commits] if commits else ["- See the diff for details."])
    lines += ["", "_Built by the superheroes showrunner._"]
    return _ensure_closes("\n".join(lines), issue)


def is_placeholder_body(prose):
    """True when the PROSE part of a PR body is `--fill-first` commit-trailer junk or blank —
    safe to replace on the adopt path. Callers pass split_prose(body)[0]; a composed/fallback
    prose ('## What changed' / 'Closes #') or owner prose is NEVER a placeholder."""
    if not prose or not prose.strip():
        return True
    p = prose.strip()
    return "Task-Id:" in p and "## What changed" not in p and "Closes #" not in p


def resolve_body(body_file, work_item, *, root=None, worktree=None, base=None,
                 issue=None, commits=None):
    """The final PROSE body: composed (if the file is usable) else the deterministic fallback,
    always scrubbed (pr_comment.scrub — the band's single scrub seam), always carrying Closes #N
    when an issue is known. Self-gathers issue/commits when not supplied. Fail-closed: an
    un-scrubbable body drops to a minimal safe body — never raw. NOTE: prose only — the caller
    owns re-attaching the #228 generated tail (split_prose / compose_body)."""
    import pr_comment
    wt = worktree or os.getcwd()
    rt = root or os.getcwd()
    if issue is None or commits is None:
        rbase = _resolve_base(wt, base)
        if commits is None:
            commits = _commits(wt, rbase)
        if issue is None:
            issue, _ = _intent(work_item, rt, wt)
    candidate = ""
    if body_file:
        try:
            with open(body_file, encoding="utf-8") as fh:
                candidate = fh.read()
        except OSError:
            candidate = ""
    if not _usable(candidate):
        candidate = fallback_body(work_item, issue, commits)
    candidate = _ensure_closes(candidate, issue)
    try:
        scrubbed = pr_comment.scrub(candidate)
    except Exception:
        scrubbed = _ensure_closes("Changes for %s (body scrub failed — see the diff)." % work_item,
                                  issue)
    return scrubbed if _usable(scrubbed) else _ensure_closes("Changes for %s." % work_item, issue)


def _cmd_resolve_body(a):
    print(resolve_body(a.body_file, a.work_item, root=a.root, worktree=a.worktree, base=a.base,
                       issue=a.issue))


def main(argv=None):
    ap = argparse.ArgumentParser(description="showrunner PR-body composer (#219)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("context")
    c.add_argument("--work-item", required=True)
    c.add_argument("--base", default=None)
    c.add_argument("--worktree", default=None)
    c.add_argument("--root", default=None)
    c.add_argument("--issue", default=None)
    c.add_argument("--body-path", default=None)
    c.set_defaults(fn=_cmd_context)
    r = sub.add_parser("resolve-body")
    r.add_argument("--work-item", required=True)
    r.add_argument("--body-file", default=None)
    r.add_argument("--base", default=None)
    r.add_argument("--worktree", default=None)
    r.add_argument("--root", default=None)
    r.add_argument("--issue", default=None)
    r.set_defaults(fn=_cmd_resolve_body)
    a = ap.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
