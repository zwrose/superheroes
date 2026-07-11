# plugins/superheroes/lib/pr_entry.py
"""draft-PR / mark-ready leaf. draft: recover.pr_action(world) -> adopt an open PR or create one
after ship_gate.decide proves build+review; returns {pr}. mark-ready: pr_phase.mark_ready_action on
a gh isDraft read -> flip if needed. Fail-closed: any 'gate' decision returns ok:false."""
import argparse, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import checkpoint as ckpt_lib, control_plane, pr_phase, recover, ship_gate, test_pilot_status
import idempotent_write, dod_gate


def _gh_pr(branch):
    try:
        r = subprocess.run(["gh", "pr", "list", "--head", branch, "--state", "all",
                            "--json", "number,url,isDraft,state"], capture_output=True, text=True, timeout=60)
    except subprocess.TimeoutExpired:
        return "unknown"                                 # a hung gh read -> transient
    if r.returncode != 0:
        return "unknown"
    try:
        arr = json.loads(r.stdout or "[]")
    except ValueError:
        return "unknown"                                 # malformed gh output -> fail closed
    return arr[0] if arr else None


def push_branch(branch, run=None, timeout=120):
    """Push the build branch to origin BEFORE PR creation. `gh pr create --head <branch>` requires
    the branch to exist on the remote, but nothing upstream pushes it — every push (reconcile-head /
    freshen / fix-push) lives in ship_phase, which runs AFTER draft-PR. Ordinary non-force push
    (FR-9, never --force / --force-with-lease); refs are shared with the build worktree, so pushing
    from the repo root reaches the branch. Idempotent: an already-pushed, up-to-date branch is a
    no-op success. Returns None on success, else a park reason string (fail-closed — the same
    park contract as the other draft failure exits)."""
    run = run or subprocess.run
    try:
        r = run(["git", "push", "origin", branch], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        # Unlike a `gh pr create` timeout, a push timeout leaves NO PR to adopt on resume (the PR
        # does not exist yet) — so "will adopt on resume" does NOT apply; a plain park is correct.
        return "branch push timed out before PR create"
    if r.returncode != 0:
        return "branch push failed before PR create: %s" % (r.stderr or "")[-300:]
    return None


# --- ship-phase honesty gates (issue #228) --------------------------------

def _spec_lookup(root, work_item):
    """(spec_present, spec_text) for the run's work-item. spec_present=False is the #25 quick
    route (a tasks doc with no spec.md) -> the DoD gate is not-applicable. A present-but-unreadable
    spec returns (True, "") so the DoD gate fail-closes (parks). Propagates
    mode_registry.UnknownSchemaVersion so the caller can fail closed on an undeterminable mode."""
    import definition_doc
    d = definition_doc.resolve_work_item_dir(work_item, root=root, cwd=root)
    spec_path = os.path.join(d, "spec.md")
    if not os.path.isfile(spec_path):
        return (False, None)
    try:
        with open(spec_path, encoding="utf-8") as fh:
            return (True, fh.read())
    except OSError:
        return (True, "")


def _gh_pr_body(number):
    """The PR's body text, or None on any unreadable read (the DoD gate fail-closes on None)."""
    if not number:
        return None
    try:
        r = subprocess.run(["gh", "pr", "view", str(number), "--json", "body", "--jq", ".body"],
                           capture_output=True, text=True, timeout=30)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    return r.stdout


def _gh_edit_body(number, body):
    """Set the PR body via `gh pr edit --body-file`. Returns the CompletedProcess (rc is the
    caller's success signal) or None on timeout. Best-effort callers (`_seed_pr_body`) ignore the
    return; the strict body-set (`_set_prose_body`, #219) reads rc to fail-close on create."""
    import tempfile
    fd, tmp = tempfile.mkstemp(prefix="pr-body-", suffix=".md")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(body)
        try:
            return subprocess.run(["gh", "pr", "edit", str(number), "--body-file", tmp],
                                  capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired:
            return None
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def _branch_diff(branch, base, root):
    """Unified diff of `branch` vs its base (three-dot: changes introduced on the branch), for
    the STUB-marker scan. Empty string on any git error (best-effort — no markers surfaced)."""
    import base_ref
    base_name = base or "main"
    resolved = base_ref.resolve_configured_base(root, base_name) or base_name
    ref = branch or "HEAD"
    try:
        r = subprocess.run(["git", "diff", "%s...%s" % (resolved, ref)],
                           capture_output=True, text=True, timeout=60, cwd=root)
    except Exception:
        return ""
    return r.stdout or "" if r.returncode == 0 else ""


def _seed_pr_body(root, work_item, branch, base, number):
    """Best-effort: seed the DoD disposition table + generated Stubbed-seams section into the PR
    body at draft time, so the build/ship legs FILL the table rather than invent it. Fail-open —
    the mark-ready DoD gate is the fail-closed enforcement, so a failed seed simply parks there.
    Never writes to stdout (the courier reads a single JSON line from it)."""
    import pr_body, stub_markers
    if not number:
        return
    spec_present, spec_text = _spec_lookup(root, work_item)
    dod_bullets = dod_gate.parse_dod_bullets(spec_text) if spec_present else None
    markers = stub_markers.markers_in_diff(_branch_diff(branch, base, root))
    dod_block = pr_body.seed_dod_block(dod_bullets or [])
    stubs_block = pr_body.stubbed_seams_block(markers)
    if not dod_block and not stubs_block:
        return
    current = _gh_pr_body(number)
    if current is None:
        sys.stderr.write("draft-PR body seed skipped: PR body unreadable\n")
        return
    new_body = pr_body.compose_body(current, dod_block, stubs_block)
    if not new_body or new_body.rstrip() == (current or "").rstrip():
        return
    _gh_edit_body(number, new_body)


def _set_prose_body(root, work_item, branch, base, number, body_file, worktree=None):
    """Set the durable "what & why" PROSE body (issue #219) on the draft PR. Returns None on
    success or a deliberate no-op, else a reason string (the caller decides park vs best-effort).

    Fail-closed read: an unreadable current body returns a reason. Adopt no-clobber: only a
    PLACEHOLDER prose (`--fill-first` commit-trailer junk / blank) is replaced — a real composed
    body or an owner-authored one is left untouched (return None, no Sonnet re-spend on resume).
    The #228 generated tail (DoD table / stubbed seams) is split off and re-attached UNCHANGED so
    a filled DoD table is never lost. The composed prose comes from `pr_body.resolve_body`
    (composed body-file if usable, else the deterministic fallback), which is always scrubbed and
    carries `Closes #N`.

    Two distinct locations (review-code finding — a build worktree conflated both): the GIT ops
    (commits/diff for the fallback body) run against the MANAGED build `worktree` the branch being
    opened lives in (the spine's --worktree / resolveBuildTarget), while definition-DOC resolution
    (issue + intent, so `Closes #N` and the "why" survive) runs against `root` — the launch
    checkout `pr_entry` ran from (couriers cd into it). This matters for in-repo GITIGNORED docs,
    which live only in the launch checkout and are absent from a fresh build-worktree checkout;
    rooting docs at the worktree there would silently drop the issue/intent. `worktree` falls back
    to `root` only when the spine could not resolve one."""
    import pr_body
    if not number:
        return None
    current = _gh_pr_body(number)
    if current is None:
        return "PR body unreadable — cannot set the prose body"
    prose, tail = pr_body.split_prose(current or "")
    if not pr_body.is_placeholder_body(prose):
        return None                                      # never clobber a real/owner prose
    new_prose = pr_body.resolve_body(body_file, work_item, root=root,
                                     worktree=(worktree or root), base=base)
    tail = (tail or "").strip()
    final = new_prose + (("\n\n" + tail) if tail else "") + "\n"
    cp = _gh_edit_body(number, final)
    if cp is None or cp.returncode != 0:
        return "gh pr edit failed to set the PR body"
    return None


def _draft_success(root, work_item, branch, base, pr, read_back, body_file, strict_body, worktree=None):
    """Set the prose body FIRST (so `_seed_pr_body` appends the DoD/stubs blocks onto real prose),
    then seed those blocks (best-effort), then emit the draft-step success JSON and exit. On the
    CREATE path (strict_body=True) a body-set failure parks fail-closed — resume adopts the PR and
    sets the body then (exactly-once preserved). On the ADOPT path (strict_body=False) a body-set
    failure is best-effort (a stderr note, like seeding)."""
    number = pr.get("number") if isinstance(pr, dict) else None
    try:
        body_reason = _set_prose_body(root, work_item, branch, base, number, body_file, worktree=worktree)
    except Exception as e:                               # a body-set crash is never a ship blocker
        body_reason = "prose body-set errored: %s" % e
    if body_reason is not None:
        if strict_body:
            print(json.dumps({"ok": False, "read_back": False, "reason": body_reason}))
            sys.exit(0)
        sys.stderr.write("draft-PR prose set skipped: %s\n" % body_reason)
    try:
        _seed_pr_body(root, work_item, branch, base, number)
    except Exception as e:                               # seeding is best-effort; never fail the draft
        sys.stderr.write("draft-PR body seed skipped: %s\n" % e)
    print(json.dumps({"ok": True, "pr": pr, "read_back": bool(read_back)}))
    sys.exit(0)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", required=True, choices=["draft", "mark-ready"])
    ap.add_argument("--work-item", required=True)
    ap.add_argument("--emit-world", action="store_true",
                    help="IO-only mode: world-read the PR and emit {pr} without judgment or creation")
    ap.add_argument("--base", default=None,
                    help="configurable PR target base branch; absent -> gh uses remote default (current behavior)")
    ap.add_argument("--body-file", default=None,
                    help="composed 'what & why' PR-body prose (#219); absent -> deterministic fallback")
    ap.add_argument("--worktree", default=None,
                    help="the MANAGED build worktree this PR's branch lives in (review-code review "
                         "finding); threaded into the prose body-set's git/doc reads so a fallback "
                         "body describes the build branch, not the launch checkout cwd defaults to")
    a = ap.parse_args(argv)
    root = os.getcwd()
    paths = control_plane.paths(root, a.work_item)
    cp = ckpt_lib.read(paths["checkpoint"])
    if isinstance(cp, dict) and cp.get("_incompatible"):
        # A durable-but-incompatible checkpoint must NOT fall back to an empty branch (that
        # lists/creates PRs against the ambient HEAD). Fail closed before any PR action.
        print(json.dumps({"ok": False,
                          "reason": "checkpoint incompatible: %s" % cp.get("reason", "unknown reason")}))
        sys.exit(0)
    cp = cp or {}
    branch = cp.get("branch", "")

    if a.step == "draft" and a.emit_world:
        # IO-only emit mode: world-read the PR and emit {pr} — no judgment, no creation. The JS twin
        # (recover.prAction) decides adopt/create/gate in-process.
        world = {"pr": _gh_pr(branch)}
        print(json.dumps(world))
        sys.exit(0)

    if a.step == "draft":
        world = {"pr": _gh_pr(branch)}
        act = recover.pr_action(world)                       # adopt | create | gate (exactly-once)
        if act == "gate":
            print(json.dumps({"ok": False, "read_back": False,
                              "reason": "PR read transient/merged — not creating a 2nd PR"})); sys.exit(0)
        if act == "adopt":
            current = _gh_pr(branch)
            read_back = isinstance(current, dict) and isinstance(world["pr"], dict) and current.get("number") == world["pr"].get("number")
            # adopt: best-effort body-set (never re-park a PR that already exists; a placeholder
            # prose is replaced, a real/owner body is left untouched).
            _draft_success(root, a.work_item, branch, a.base, world["pr"], read_back,
                           a.body_file, strict_body=False, worktree=a.worktree)
        # create: only after the ship-gate proves SDD build + review-code ran over the SHIPPED HEAD —
        # the build branch's tip (what the PR ships), resolved from checkpoint.branch, not the cwd HEAD.
        try:
            _hp = subprocess.run(["git", "rev-parse", branch or "HEAD"], capture_output=True, text=True, timeout=10)
        except subprocess.TimeoutExpired:
            print(json.dumps({"ok": False, "reason": "git rev-parse timed out"})); sys.exit(0)
        head = _hp.stdout.strip()
        if _hp.returncode != 0 or not head:
            print(json.dumps({"ok": False, "reason": "cannot resolve branch HEAD for the ship-gate"})); sys.exit(0)
        try:
            prov = ship_gate.read_provenance(paths["provenance"])
        except ship_gate.ProvenanceError as e:           # corrupt provenance.json -> gate (fail closed)
            print(json.dumps({"ok": False, "reason": "provenance unreadable: %s" % e})); sys.exit(0)
        from review_result import read_result
        # premortem-001: fold in the run's journal `build:` denial events as a SECOND carrier —
        # either carrier gates. A journal read error swallows to [] inside the helper (fail-safe
        # toward the provenance carrier).
        _jdenials = ship_gate.journal_build_denials(paths["events"])
        decision = ship_gate.decide(prov, read_result(paths["review_result"]), head,
                                    journal_denials=_jdenials)
        if decision["action"] != "proceed":
            print(json.dumps({"ok": False, "reason": decision["reason"]})); sys.exit(0)
        # Push the build branch before creating the PR (see push_branch): `gh pr create --head` needs
        # the branch on origin, but every ship_phase push runs AFTER this step. On any failure, park
        # fail-closed — on resume recover.pr_action re-pushes (no-op) then creates (exactly-once holds).
        _push_park = push_branch(branch)
        if _push_park is not None:
            print(json.dumps({"ok": False, "read_back": False, "reason": _push_park})); sys.exit(0)
        # Build the gh pr create command. When --base is supplied, pass it explicitly so the
        # PR targets the configured base (not the remote default). Absent -> omit (default behavior).
        # --fill-first (not --fill): derive the title from the FIRST commit's subject. `--fill` uses the
        # branch NAME as the title for a multi-commit branch, which is not a Conventional Commit and fails
        # a conventional-title CI check (blocking ship); the build's first commit subject IS conventional.
        _gh_create_cmd = ["gh", "pr", "create", "--draft", "--fill-first", "--head", branch]
        if a.base:
            _gh_create_cmd.extend(["--base", a.base])
        try:
            out = subprocess.run(_gh_create_cmd, capture_output=True, text=True, timeout=120)
        except subprocess.TimeoutExpired:
            # the create may have landed server-side -> park; recover.pr_action adopts it on resume.
            print(json.dumps({"ok": False, "read_back": False, "reason": "gh pr create timed out — will adopt on resume"})); sys.exit(0)
        if out.returncode != 0:
            # Surface a bounded tail of gh's stderr so a parked create is diagnosable (not a bare
            # "gh pr create failed" with no cause).
            print(json.dumps({"ok": False, "read_back": False,
                              "reason": "gh pr create failed: %s" % (out.stderr or "")[-300:]})); sys.exit(0)
        # Read the just-created PR back. A transient read failure must NOT be recorded as ok:true with
        # pr=null (that loses the PR for ship/mark-ready, and the readout never reaches the PR thread).
        # Park instead — on resume recover.pr_action adopts the now-existing PR (exactly-once preserved).
        pr = _gh_pr(branch)
        if not isinstance(pr, dict):
            print(json.dumps({"ok": False, "read_back": False,
                              "reason": "PR created but read-back failed transiently — will adopt on resume"}))
            sys.exit(0)
        current = _gh_pr(branch)
        read_back = isinstance(current, dict) and current.get("number") == pr.get("number")
        # create: strict body-set — a failed set parks fail-closed (resume adopts and sets it).
        _draft_success(root, a.work_item, branch, a.base, pr, read_back,
                       a.body_file, strict_body=True, worktree=a.worktree)
    else:  # mark-ready
        pr = _gh_pr(branch)
        decision = pr_phase.mark_ready_action(pr)
        if decision == "gate":
            print(json.dumps({"ok": False, "read_back": False, "reason": "PR isDraft unreadable — not flipping blind"})); sys.exit(0)
        try:
            _hp = subprocess.run(["git", "rev-parse", branch or "HEAD"], capture_output=True, text=True, timeout=10)
        except subprocess.TimeoutExpired:
            print(json.dumps({"ok": False, "reason": "git rev-parse timed out"})); sys.exit(0)
        head = _hp.stdout.strip()
        if _hp.returncode != 0 or not head:
            print(json.dumps({"ok": False, "read_back": False, "reason": "cannot resolve branch HEAD for test-pilot status"})); sys.exit(0)
        status_result = test_pilot_status.assert_current(test_pilot_status.status_path(root, a.work_item), head)
        status_decision = pr_phase.mark_ready_status_action(status_result)
        if status_decision["action"] == "gate":
            print(json.dumps({"ok": False, "read_back": False, "reason": status_decision["reason"]})); sys.exit(0)
        if decision == "flip":
            # DoD disposition gate (issue #228): before the FIRST ready flip, every spec
            # Definition-of-done bullet must be disposed (done+evidence or deferred+issue) in the
            # PR body. Fail-closed — a spec-less quick route (#25) is not-applicable and passes; a
            # spec present with an unaddressed bullet, an unreadable body, or an undeterminable
            # store mode parks the run (never flips ready). Runs only on the flip (an already-ready
            # PR on resume is not re-gated).
            try:
                _spec_present, _spec_text = _spec_lookup(root, a.work_item)
            except Exception as e:
                print(json.dumps({"ok": False, "read_back": False,
                                  "reason": "DoD gate: spec location undeterminable (%s) — fail closed" % e})); sys.exit(0)
            _dod_bullets = dod_gate.parse_dod_bullets(_spec_text) if _spec_present else None
            _body = _gh_pr_body(pr.get("number"))
            if _spec_present and _body is None:
                print(json.dumps({"ok": False, "read_back": False,
                                  "reason": "DoD gate: PR body unreadable — fail closed"})); sys.exit(0)
            _dod = dod_gate.decide(_dod_bullets, _body or "", spec_present=_spec_present)
            if _dod["verdict"] == "park":
                # "gate"/"pr" are machine fields for the bundle's mark-ready leg: the
                # disposition-FILLER leaf (issue #228's "build/ship legs fill it" — found
                # missing live in the 0.10.0 qualification) dispatches only when gate ==
                # "dod", then this decider re-decides over the filled table. Matching on
                # the reason STRING in JS would copy dod_gate's wording across the
                # boundary (CONVENTIONS §11); this field is the single contract instead.
                print(json.dumps({"ok": False, "read_back": False, "gate": "dod",
                                  "pr": pr.get("number"),
                                  "reason": "DoD gate: %s" % _dod["reason"]})); sys.exit(0)
            n = str(pr["number"])

            def _reader():
                cur = _gh_pr(branch)
                if not isinstance(cur, dict):
                    return (None, "PR isDraft unreadable")
                d = cur.get("isDraft")
                if d is False:
                    return (True, "already ready")
                if d is True:
                    return (False, "draft")
                return (None, "isDraft ambiguous")

            def _apply():
                try:
                    rc = subprocess.run(["gh", "pr", "ready", n], capture_output=True, timeout=60).returncode
                except subprocess.TimeoutExpired:
                    return (False, "gh pr ready timed out — PR still draft")
                return (rc == 0, "flipped to ready")

            res = idempotent_write.idempotent_apply("ready:pr=%s" % n, _reader, _apply)
            if not res["ok"]:
                print(json.dumps({"ok": False, "read_back": False, "reason": res["reason"] or "gh pr ready failed — PR still draft"}))
                sys.exit(0)
        current = _gh_pr(branch)
        read_back = isinstance(current, dict) and current.get("isDraft") is False
        print(json.dumps({"ok": True, "read_back": bool(read_back)}))


if __name__ == "__main__":
    main()
