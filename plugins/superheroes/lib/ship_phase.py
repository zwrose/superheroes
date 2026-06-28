# plugins/superheroes/lib/ship_phase.py
import argparse, json, os, subprocess, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import freshness, ci_loop, control_plane, journal, ci_status, checkpoint as ckpt_lib


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
ap.add_argument("--step", required=True, choices=["freshness", "ci"])
ap.add_argument("--work-item", required=True)
ap.add_argument("--emit-checks", action="store_true",
                help="IO-only mode: emit raw checks array (or {error:...}) without classifying")
a = ap.parse_args()

if a.step == "freshness":
    # is the branch up to date with base = does HEAD contain origin/<base> = is origin/<base> an
    # ancestor of HEAD. (rc 0 = yes/up-to-date, 1 = behind, other = unreadable -> gate.)
    base = "main"
    try:
        rc = subprocess.run(["git", "merge-base", "--is-ancestor", f"origin/{base}", "HEAD"],
                            capture_output=True, timeout=10).returncode
    except subprocess.TimeoutExpired:
        rc = 2                                           # a hung read -> unreadable -> freshness gate
    is_anc = True if rc == 0 else (False if rc == 1 else None)
    decision, _reason = freshness.decide(is_anc, 1)
    print(json.dumps({"decision": decision}))
elif a.emit_checks:
    # IO-only emit mode: resolve PR + run gh pr checks, emit raw checks array for the JS twin to
    # classify in-process. Emits {error:...} when the PR cannot be resolved (fail-closed signal).
    pr = _resolve_pr_number(a.work_item)
    if not pr:
        print(json.dumps({"error": "CI status could not be read"}))
    else:
        try:
            out = subprocess.run(["gh", "pr", "checks", pr, "--json", "name,bucket,state"],
                                 capture_output=True, text=True, timeout=30)
            # gh pr checks exits non-zero when checks are failing/pending; JSON is still on stdout.
            checks = json.loads(out.stdout) if out.stdout.strip() else []
        except Exception:
            checks = []
        print(json.dumps(checks))
else:
    # Real CI read: classify the PR's checks (green / red / none) via ci_status. Fail-CLOSED — any
    # read error returns 'red' (never 'green'), so ship never posts a false "merge-ready: CI green".
    print(json.dumps(_read_ci(a.work_item)))
