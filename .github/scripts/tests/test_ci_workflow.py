import os
import re

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_CI_WF = os.path.join(_ROOT, ".github", "workflows", "ci.yml")
_PR_TITLE_WF = os.path.join(_ROOT, ".github", "workflows", "pr-title.yml")
_RELEASE_WF = os.path.join(_ROOT, ".github", "workflows", "release-please.yml")


def _ci_text():
    with open(_CI_WF) as fh:
        return fh.read()


def _ci_data():
    import yaml
    with open(_CI_WF) as fh:
        return yaml.safe_load(fh)


def _pr_title_data():
    import yaml
    with open(_PR_TITLE_WF) as fh:
        return yaml.safe_load(fh)


def test_ci_concurrency_cancels_pr_runs_not_main():
    # Axis: superseded PR runs cancel; main pushes queue without cancellation.
    data = _ci_data()
    conc = data.get("concurrency", {})
    group = conc.get("group", "")
    assert "github.workflow" in group and "github.ref" in group
    cancel = conc.get("cancel-in-progress", "")
    assert "refs/heads/main" in cancel


def test_ci_pull_request_types_exclude_edited():
    # Axis: title/body edits must not re-run code checks (run economy).
    data = _ci_data()
    on = data.get(True, data.get("on"))
    types = on["pull_request"]["types"]
    assert "edited" not in types
    assert "opened" in types
    assert "synchronize" in types
    assert "reopened" in types


def test_pr_title_workflow_job_and_types():
    # Axis: required pr-title context name and event types for ruleset attachment.
    assert os.path.isfile(_PR_TITLE_WF)
    data = _pr_title_data()
    on = data.get(True, data.get("on"))
    types = on["pull_request"]["types"]
    assert "edited" in types
    assert "synchronize" in types
    jobs = data["jobs"]
    assert "pr-title" in jobs
    assert jobs["pr-title"]["name"] == "pr-title"


def test_ci_validate_job_present():
    # Axis: validate required context remains in ci.yml.
    data = _ci_data()
    assert "validate" in data["jobs"]
    assert data["jobs"]["validate"]["name"] == "validate"


def test_ci_no_pr_title_job():
    # Axis: pr-title check lives in exactly one workflow.
    data = _ci_data()
    assert "pr-title" not in data["jobs"]


def test_ci_permissions_include_pull_requests_read():
    # Axis: check_release_bump.py needs pull-requests API scope.
    data = _ci_data()
    perms = data.get("permissions", {})
    assert perms.get("pull-requests") == "read"


def test_release_bump_gate_step_gated_on_release_branch():
    # Axis: gate mis-targeting — step must run only on release-please PRs.
    data = _ci_data()
    steps = data["jobs"]["validate"]["steps"]
    gate = next(s for s in steps if "Pre-merge release-bump gate" in (s.get("name") or ""))
    if_cond = gate.get("if", "")
    assert "github.event_name == 'pull_request'" in if_cond
    assert "release-please--branches--main--components--superheroes" in if_cond
    run = gate.get("run", "")
    assert "check_release_bump.py" in run
    assert "git fetch --tags" in run


def test_release_bump_gate_uses_base_sha():
    # Axis: gate compares proposal against last released state, not PR head manifest.
    data = _ci_data()
    steps = data["jobs"]["validate"]["steps"]
    gate = next(s for s in steps if "Pre-merge release-bump gate" in (s.get("name") or ""))
    assert "github.event.pull_request.base.sha" in gate.get("run", "")


def test_release_bump_gate_sets_gh_token():
    # Axis: scope grant is not authentication — GH_TOKEN must be set.
    data = _ci_data()
    steps = data["jobs"]["validate"]["steps"]
    gate = next(s for s in steps if "Pre-merge release-bump gate" in (s.get("name") or ""))
    assert gate.get("env", {}).get("GH_TOKEN") == "${{ secrets.GITHUB_TOKEN }}"


def test_validate_installs_all_coupling_collectors():
    # Axis: silent-skip return — collectors must be installed so real-seam tests cannot degrade.
    text = _ci_text()
    assert "dependency-cruiser" in text
    assert "typescript" in text
    assert "import-linter" in text


def test_release_please_still_runs_check_release_bump():
    # Axis: post-merge backstop was not removed.
    with open(_RELEASE_WF) as fh:
        text = fh.read()
    assert "check_release_bump.py" in text
