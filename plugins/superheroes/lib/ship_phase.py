# plugins/superheroes/lib/ship_phase.py
import argparse, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import freshness, ci_loop, control_plane, journal, ci_status, checkpoint as ckpt_lib, base_ref
import idempotent_write, ship_reconcile


def _resolve_pr_number(work_item):
    """The run's PR number from the recorded checkpoint, else from `gh pr view`. None on any error."""
    try:
        paths = control_plane.paths(os.getcwd(), work_item)
        cp = ckpt_lib.read(paths["checkpoint"]) or {}
        pr = cp.get("pr")
        if isinstance(pr, dict) and pr.get("number"):
            return str(pr["number"])
    except Exception:
        pass
    try:
        out = subprocess.run(["gh", "pr", "view", "--json", "number", "--jq", ".number"],
                             capture_output=True, text=True, timeout=10)
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except Exception:
        pass
    return None


def _git(args, cwd=None):
    """(rc, stdout). A timeout/raise -> (2, '') so callers fail closed."""
    try:
        r = subprocess.run(["git", *args], capture_output=True, text=True, cwd=cwd, timeout=60)
        return r.returncode, (r.stdout or "").strip()
    except Exception:
        return 2, ""


def _local_head(cwd=None):
    rc, out = _git(["rev-parse", "HEAD"], cwd=cwd)
    return out if rc == 0 and out else None


def _remote_pr_head(work_item):
    """The PR's current remote head SHA via gh, or None on any unreadable read (fail closed)."""
    pr = _resolve_pr_number(work_item)
    if not pr:
        return None
    try:
        r = subprocess.run(["gh", "pr", "view", pr, "--json", "headRefOid", "--jq", ".headRefOid"],
                           capture_output=True, text=True, timeout=30)
    except Exception:
        return None
    if r.returncode != 0:
        return None
    return r.stdout.strip() or None


def _read_ci(work_item):
    """Real CI read -> {"decision": green|red|none, "reason": text, "failing": [...]}. Fail-CLOSED:
    any read error -> red (never green)."""
    pr = _resolve_pr_number(work_item)
    if not pr:
        return {"decision": "red", "reason": "CI status could not be read"}
    try:
        out = subprocess.run(["gh", "pr", "checks", pr, "--json", "name,bucket,state"],
                             capture_output=True, text=True, timeout=30)
        # `gh pr checks` exits non-zero when checks are failing/pending; the JSON is still on stdout,
        # so parse stdout regardless of returncode and let ci_status classify.
        checks = json.loads(out.stdout) if out.stdout.strip() else []
    except Exception:
        return {"decision": "red", "reason": "CI status could not be read"}
    res = ci_status.classify(checks)
    status = res["status"]
    if status == "green":
        return {"decision": "green", "reason": "all required checks pass", "failing": []}
    if status == "none":
        return {"decision": "none",
                "reason": "no required checks gate this PR — confirm checks before merging",
                "failing": []}
    return {"decision": "red",
            "reason": "checks not green: %s" % ", ".join(res["failing"]),
            "failing": res["failing"]}

ap = argparse.ArgumentParser()
ap.add_argument("--step", required=True,
                choices=["freshness", "ci", "reconcile-head", "freshen", "ci-decide",
                         "ci-record", "fix-push", "revert-draft"])
ap.add_argument("--work-item", required=True)
ap.add_argument("--emit-checks", action="store_true",
                help="IO-only mode: emit raw checks array (or {error:...}) without classifying")
ap.add_argument("--base", default=None,
                help="configurable base branch name; absent -> default 'main' (current behavior)")
ap.add_argument("--attempt", type=int, default=1,
                help="1-based catch-up attempt threaded into freshness.decide (default 1)")
ap.add_argument("--worktree", default=None,
                help="the build worktree the git mechanics run in; absent -> cwd")
a = ap.parse_args()

if a.step == "freshness":
    # is the branch up to date with base = does HEAD contain <base> = is <base> an ancestor of HEAD.
    # (rc 0 = yes/up-to-date, 1 = behind, other = unreadable -> gate.)
    # FR-8: --base is a caller-supplied branch name (e.g. 'live-showrunner-102' or 'main').
    # Default to 'main' when absent so existing behavior is unchanged.
    wt = a.worktree or os.getcwd()
    base_name = a.base if a.base else "main"
    # C-I1: resolve the base via the SHARED resolver (local->origin), rooted in the worktree.
    resolved = base_ref.resolve_configured_base(wt, base_name)
    if resolved is None:
        print(json.dumps({"decision": "gate",
                          "reason": base_ref.unresolvable_reason(base_name, wt)}))
    else:
        try:
            rc = subprocess.run(["git", "merge-base", "--is-ancestor", resolved, "HEAD"],
                                capture_output=True, timeout=10, cwd=wt).returncode
        except subprocess.TimeoutExpired:
            rc = 2                                       # a hung read -> unreadable -> freshness gate
        is_anc = True if rc == 0 else (False if rc == 1 else None)
        decision, _reason = freshness.decide(is_anc, a.attempt)
        print(json.dumps({"decision": decision}))
elif a.step == "reconcile-head":
    # UFR-6: bring the remote PR head into agreement with the reconciled local head by pushing
    # local-ahead. The reader=(remote==local)/applier=push WIRING lives in the pure ship_reconcile
    # decider (testable without gh); this leaf only does the gh/git IO.
    wt = a.worktree or os.getcwd()
    local = _local_head(wt)
    if not local:
        print(json.dumps({"ok": False, "head": None, "reason": "local HEAD unreadable — fail closed"}))
        sys.exit(0)
    paths = control_plane.paths(os.getcwd(), a.work_item)
    cp = ckpt_lib.read(paths["checkpoint"]) or {}
    branch = cp.get("branch") or ""

    def _push():
        rc, _ = _git(["push", "origin", branch], cwd=wt)          # ordinary non-force push (FR-9)
        if rc != 0:
            return False
        return _remote_pr_head(a.work_item) == local              # read-back-confirm the push landed

    res = ship_reconcile.reconcile_head(local, _remote_pr_head(a.work_item), branch, _push)
    print(json.dumps({"ok": bool(res["ok"]),
                      "head": local if res["ok"] else None,
                      "reason": res["reason"]}))
elif a.emit_checks:
    # IO-only emit mode: resolve PR + run gh pr checks, emit raw checks array for the JS twin to
    # classify in-process. Emits {error:...} when the PR cannot be resolved (fail-closed signal).
    pr = _resolve_pr_number(a.work_item)
    if not pr:
        print(json.dumps({"error": "CI status could not be read"}))
    else:
        # Mirror _read_ci's fail-closed posture: a read that genuinely FAILS (the gh subprocess
        # raised/errored, OR stdout was non-empty-but-unparseable) emits the {error:...} sentinel
        # the JS twin parks on. Emit [] ONLY for a genuinely-successful read with no checks (an
        # empty stdout from a successful gh call). Never coerce a failed/garbled read to [] — that
        # would classify 'none' downstream and post a false "merge-ready: no required checks".
        try:
            out = subprocess.run(["gh", "pr", "checks", pr, "--json", "name,bucket,state"],
                                 capture_output=True, text=True, timeout=30)
        except Exception:
            print(json.dumps({"error": "CI status could not be read"}))
        else:
            # gh pr checks exits non-zero when checks are failing/pending; JSON is still on stdout.
            raw = out.stdout.strip()
            if not raw:
                print(json.dumps([]))            # successful read, no checks gate this PR
            else:
                try:
                    checks = json.loads(raw)
                except Exception:
                    print(json.dumps({"error": "CI status could not be read"}))  # unparseable -> fail-closed
                else:
                    print(json.dumps(checks))
else:
    # Real CI read: classify the PR's checks (green / red / none) via ci_status. Fail-CLOSED — any
    # read error returns 'red' (never 'green'), so ship never posts a false "merge-ready: CI green".
    print(json.dumps(_read_ci(a.work_item)))
