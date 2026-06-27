"""Deterministic pre-flight gate for the showrunner launch (FR-9). Pure decide() over a
probes dict (so it is unit-testable), plus a best-effort probe() that fills probes from the
band's existing surfaces, plus a JSON main(). Fail-CLOSED: a check that errors or cannot be
evaluated is treated as not-passing.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# blocking check key -> (human cause when failing, remediation)
_REM = {
    "spec-approved": "approve the spec first (run discovery to the owner's sign-off)",
    "github-access": "fix GitHub access, then retry (see the gh-access note)",
    "no-active-run": "wait for the in-progress run to finish or park, then relaunch",
    "repo-ready": "ensure this is a git repo whose base branch exists and whose remote is reachable",
    "verify-resolves": "configure the project's verify/test command in the review profile",
    "config-resolves": "run the band's init so the profile + storage config resolve",
}


def _fail(check, status, remediation):
    return {"check": check, "status": status, "cause": _REM[check], "remediation": remediation or _REM[check]}


def decide(probes, work_item):
    """Pure verdict over the probes dict. ok iff every blocking check passes."""
    if not isinstance(probes, dict):
        probes = {}
    blocking = []

    if probes.get("spec_gate") == "passed":
        blocking.append({"check": "spec-approved", "status": "pass"})
    else:
        blocking.append(_fail("spec-approved", "fail", _REM["spec-approved"]))

    gh = probes.get("gh") or {}
    if gh.get("ok") is True:
        blocking.append({"check": "github-access", "status": "pass"})
    else:
        status = "indeterminate" if gh.get("cause") == "indeterminate" else "fail"
        blocking.append(_fail("github-access", status, gh.get("remediation")))

    active = probes.get("active_run")
    # active = none | parked | stale | finished  -> pass; any other value = a live run for another
    # work-item (or this one already live) -> block (the spec's "no conflicting active run").
    if active in (None, "none", "parked", "stale", "finished"):
        blocking.append({"check": "no-active-run", "status": "pass"})
    else:
        blocking.append(_fail("no-active-run", "fail", _REM["no-active-run"]))

    for key, check in (("repo_ready", "repo-ready"), ("verify_resolves", "verify-resolves"),
                       ("config_resolves", "config-resolves")):
        val = probes.get(key)
        if val is True:
            blocking.append({"check": check, "status": "pass"})
        elif val is False:
            blocking.append(_fail(check, "fail", _REM[check]))
        else:                                   # None/unknown -> fail-closed indeterminate
            blocking.append(_fail(check, "indeterminate", _REM[check]))

    advisory = []
    ci = probes.get("ci") or {}
    if not (ci.get("provider") and ci.get("required")):
        advisory.append({"check": "ci-visibility",
                         "note": "no required CI gates this PR — the run will produce a pull request "
                                 "but hand it back for you to confirm checks before merging."})

    ok = all(b["status"] == "pass" for b in blocking)
    return {"ok": ok, "blocking": blocking, "advisory": advisory}


def _lease_state(cwd, other_work_item, root):
    """The string "live" iff `other_work_item` holds a fresh (non-stale) ref_lock lease,
    else "stale" (fail-closed: any error -> "stale", so the relaunch is never falsely blocked).
    Resolve the control-plane store FIRST (the dir ref_lock reads leases from) — passing cwd
    as the store would make every lease read come back absent."""
    try:
        import control_plane
        import ref_lock
        store = control_plane.checkout_dir(cwd, root)
        _sha, lease = ref_lock.read_lease(store, other_work_item)
        if isinstance(lease, dict) and not ref_lock.is_stale(lease, ref_lock.DEFAULT_TTL):
            return "live"
        return "stale"
    except Exception:
        return "stale"


def _repo_ready(root):
    """True iff this is a git repo whose base branch resolves and whose remote is reachable."""
    try:
        import subprocess
        def _git(*args):
            return subprocess.run(["git", "-C", root, *args],
                                  capture_output=True, text=True, timeout=10)
        inside = _git("rev-parse", "--is-inside-work-tree")
        if inside.returncode != 0 or inside.stdout.strip() != "true":
            return False
        # base branch resolves: origin/HEAD (the default branch) or a local HEAD ref.
        head = _git("symbolic-ref", "--quiet", "refs/remotes/origin/HEAD")
        if head.returncode != 0 or not head.stdout.strip():
            head = _git("rev-parse", "--abbrev-ref", "HEAD")
            if head.returncode != 0 or not head.stdout.strip():
                return False
        # remote reachable: a configured remote (cheap ls-remote against origin).
        remote = _git("remote")
        if remote.returncode != 0 or not remote.stdout.strip():
            return False
        ls = _git("ls-remote", "--exit-code", "origin", "HEAD")
        return ls.returncode == 0
    except Exception:
        return False


def _verify_resolves(root):
    """True iff verify_command_cli resolves a command OR the profile is explicitly `unverified`.
    Fail-closed: any error -> False."""
    try:
        import subprocess
        here = os.path.dirname(os.path.abspath(__file__))
        out = subprocess.run([sys.executable, os.path.join(here, "verify_command_cli.py")],
                             capture_output=True, text=True, cwd=root, timeout=30)
        if out.returncode != 0:
            return False
        obj = json.loads(out.stdout or "{}")
        cmd = obj.get("command")
        return bool(cmd) and cmd not in ("none", None)
    except Exception:
        return False


def _config_resolves(root):
    """True iff the band's policy + storage-mode reads complete without error. Fail-closed.

    READ-ONLY: uses `mode_registry.read_registry` (not `resolve`, which backfills/creates a
    store as a side-effect) so a readiness check never mutates state. A legitimately-absent
    config is fine — the later phases fall back to provisional defaults — so this only fails
    on an UNREADABLE config (an IO error, or `read_registry` raising UnknownSchemaVersion on
    a too-new schema, which is the fail-closed case the later phases genuinely can't proceed past).
    """
    try:
        import architect_config
        import mode_registry
        cwd = os.getcwd()
        architect_config.read_policy(cwd, root)   # None on absent/corrupt; raises only on real IO error
        mode_registry.read_registry(cwd, root)    # read-only; raises UnknownSchemaVersion (fail-closed)
        return True
    except Exception:
        return False


def _ci_required(root, ci):
    """True iff the base branch's protection requires >0 status checks. Fail-closed (False on any error)."""
    try:
        import subprocess
        slug = subprocess.run(
            ["gh", "repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner"],
            capture_output=True, text=True, cwd=root, timeout=10)
        if slug.returncode != 0 or not slug.stdout.strip():
            return False
        repo = slug.stdout.strip()
        base = subprocess.run(
            ["gh", "repo", "view", "--json", "defaultBranchRef", "--jq", ".defaultBranchRef.name"],
            capture_output=True, text=True, cwd=root, timeout=10)
        branch = base.stdout.strip() if base.returncode == 0 else ""
        if not branch:
            return False
        out = subprocess.run(
            ["gh", "api", "repos/%s/branches/%s/protection" % (repo, branch),
             "--jq", ".required_status_checks.checks | length"],
            capture_output=True, text=True, cwd=root, timeout=10)
        if out.returncode != 0:
            return False
        return int((out.stdout or "0").strip() or "0") > 0
    except Exception:
        return False


def probe(work_item, root):
    """Best-effort world-read -> probes dict. NEVER raises; an unreadable check stays unknown
    (-> fail-closed in decide)."""
    import subprocess
    import gh_preflight, control_plane, detect
    p = {}
    try:
        # definition_doc exposes read_gate(path) + a `read-gate` CLI; shell the CLI (the verified
        # interface) so we don't guess the path-builder. It prints the gate value ("passed"/"pending"/…).
        here = os.path.dirname(os.path.abspath(__file__))
        out = subprocess.run(
            ["python3", os.path.join(here, "definition_doc.py"), "read-gate",
             "--doc", "spec", "--work-item", work_item, "--root", root],
            capture_output=True, text=True, timeout=10)
        p["spec_gate"] = out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        p["spec_gate"] = None
    try:
        gp = gh_preflight.probe(root)
        ok, cause, rem = gh_preflight.decide(gp, required="write")
        p["gh"] = {"ok": ok, "cause": cause, "remediation": rem}
    except Exception as exc:
        p["gh"] = {"ok": False, "cause": "indeterminate", "remediation": "verify GitHub is reachable and retry"}
    try:
        cur = control_plane.get_current(os.getcwd(), root)
        # current run is this work-item or none -> not a conflict; another work-item -> check its lease.
        p["active_run"] = "none" if (cur is None or cur == work_item) else _lease_state(os.getcwd(), cur, root)
    except Exception:
        p["active_run"] = None
    p["repo_ready"] = _repo_ready(root)
    p["verify_resolves"] = _verify_resolves(root)
    p["config_resolves"] = _config_resolves(root)
    try:
        ci = detect.detect_ci(root)
        p["ci"] = {"provider": ci.get("provider"), "required": _ci_required(root, ci)}
    except Exception:
        p["ci"] = {"provider": None, "required": False}
    return p


def _parse_args(argv):
    """(work_item, root) from `--work-item <wi>` / `--root <dir>`; defaults None / '.'."""
    work_item, root = None, "."
    i = 0
    while i < len(argv):
        if argv[i] == "--work-item" and i + 1 < len(argv):
            work_item = argv[i + 1]
            i += 2
            continue
        if argv[i] == "--root" and i + 1 < len(argv):
            root = argv[i + 1]
            i += 2
            continue
        i += 1
    return work_item, root


def main(argv):
    """probe -> decide -> JSON verdict on stdout. Exit 0 iff ok. ALWAYS emits a JSON verdict —
    an internal error prints a fail-CLOSED verdict so the remediation is never lost to a traceback."""
    try:
        work_item, root = _parse_args(argv)
        probes = probe(work_item, root)
        verdict = decide(probes, work_item)
    except Exception as exc:  # fail-CLOSED catch-all
        verdict = decide({}, None)
        verdict["error"] = "%s: %s" % (type(exc).__name__, exc)
    sys.stdout.write(json.dumps(verdict) + "\n")
    return 0 if verdict["ok"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
