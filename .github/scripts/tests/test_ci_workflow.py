import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.abspath(os.path.join(_HERE, "..", "..", ".."))
_CI_WF = os.path.join(_ROOT, ".github", "workflows", "ci.yml")
_PR_TITLE_WF = os.path.join(_ROOT, ".github", "workflows", "pr-title.yml")
_RELEASE_WF = os.path.join(_ROOT, ".github", "workflows", "release-please.yml")
_RELEASE_CONFIG = os.path.join(_ROOT, "release-please-config.json")
_PKG = "plugins/superheroes"

_LIB = os.path.join(_ROOT, _PKG, "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import guardian_coupling_adapters as adapters  # noqa: E402


def _ci_data():
    import yaml
    with open(_CI_WF) as fh:
        return yaml.safe_load(fh)


def _pr_title_data():
    import yaml
    with open(_PR_TITLE_WF) as fh:
        return yaml.safe_load(fh)


def _run_without_comments(run: str) -> str:
    """Executable run text only — # comment lines are not shell commands."""
    return "\n".join(
        line for line in run.splitlines() if not line.strip().startswith("#")
    )


def _validate_step_run(data, step_name_substring: str) -> str:
    steps = data["jobs"]["validate"]["steps"]
    step = next(s for s in steps if step_name_substring in (s.get("name") or ""))
    return _run_without_comments(step.get("run", ""))


def _release_branch_name() -> str:
    with open(_RELEASE_CONFIG) as fh:
        cfg = json.load(fh)
    component = cfg["packages"][_PKG]["component"]
    return f"release-please--branches--main--components--{component}"


def test_ci_concurrency_cancels_pr_runs_not_main():
    # Axis: superseded PR runs cancel; main pushes queue without cancellation.
    data = _ci_data()
    conc = data.get("concurrency", {})
    group = conc.get("group", "")
    assert "github.workflow" in group and "github.ref" in group
    cancel = conc.get("cancel-in-progress", "")
    assert isinstance(cancel, str), (
        f"cancel-in-progress must be a string expression, got {type(cancel).__name__}"
    )
    normalized = " ".join(cancel.split())
    assert re.search(
        r"github\.ref\s*!=\s*['\"]refs/heads/main['\"]", normalized
    ), (
        "cancel-in-progress must express cancel unless ref is refs/heads/main, "
        f"got: {cancel!r}"
    )


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


def test_pr_title_workflow_runs_conventional_commit_check():
    # Axis: pr-title job must enforce Conventional Commit title, not just exist.
    data = _pr_title_data()
    steps = data["jobs"]["pr-title"]["steps"]
    step = next(s for s in steps if "Conventional Commit" in (s.get("name") or ""))
    run = step.get("run", "")
    assert ".github/scripts/check_conventional_commit.py" in run
    assert "PR_TITLE" in run
    assert step.get("env", {}).get("PR_TITLE") == "${{ github.event.pull_request.title }}"


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
    branch = _release_branch_name()
    assert "github.event_name == 'pull_request'" in if_cond
    assert branch in if_cond
    run = _run_without_comments(gate.get("run", ""))
    assert "check_release_bump.py" in run
    assert "git fetch --tags" in run


def test_release_pr_install_smoke_gated_on_release_branch():
    # Axis: smoke test must track the same release-please branch name as the gate.
    data = _ci_data()
    steps = data["jobs"]["validate"]["steps"]
    smoke = next(s for s in steps if "Release-PR install smoke test" in (s.get("name") or ""))
    if_cond = smoke.get("if", "")
    branch = _release_branch_name()
    assert "github.event_name == 'pull_request'" in if_cond
    assert branch in if_cond


def test_release_bump_gate_unrefreshes_shallow_history():
    # Axis: shallow repo after catalog-membership fetch must be unshallowed before gate runs.
    data = _ci_data()
    run = _validate_step_run(data, "Pre-merge release-bump gate")
    assert "git rev-parse --is-shallow-repository" in run
    assert "--unshallow" in run


def test_release_bump_gate_refuses_still_shallow_repo():
    # Axis: fail-closed — gate must exit non-zero if still shallow after repair.
    data = _ci_data()
    run = _validate_step_run(data, "Pre-merge release-bump gate")
    assert "still shallow" in run.lower()
    assert "exit 1" in run


def test_release_bump_gate_uses_base_sha():
    # Axis: gate compares proposal against last released state, not PR head manifest.
    data = _ci_data()
    steps = data["jobs"]["validate"]["steps"]
    gate = next(s for s in steps if "Pre-merge release-bump gate" in (s.get("name") or ""))
    env = gate.get("env", {})
    assert env.get("BASE_SHA") == "${{ github.event.pull_request.base.sha }}"
    run = _run_without_comments(gate.get("run", ""))
    assert '"$BASE_SHA"' in run


def test_release_bump_gate_sets_gh_token():
    # Axis: scope grant is not authentication — GH_TOKEN must be set.
    data = _ci_data()
    steps = data["jobs"]["validate"]["steps"]
    gate = next(s for s in steps if "Pre-merge release-bump gate" in (s.get("name") or ""))
    assert gate.get("env", {}).get("GH_TOKEN") == "${{ secrets.GITHUB_TOKEN }}"


def test_validate_installs_all_coupling_collectors():
    # Axis: silent-skip return — collectors must be installed so real-seam tests cannot degrade.
    data = _ci_data()
    python_deps_run = _validate_step_run(
        data, "Install Python dependencies (validators + tests + import-linter)"
    )
    collectors_run = _validate_step_run(
        data, "Install coupling collectors (ungate coupling lens real-seam tests)"
    )
    assert "import-linter" in python_deps_run
    assert "dependency-cruiser" in collectors_run
    assert "typescript" in collectors_run


def test_ci_collector_pins_match_guardian_adapters():
    # Axis: ci.yml install majors must track guardian_coupling_adapters pins (CONVENTIONS §11.3).
    data = _ci_data()
    python_deps_run = _validate_step_run(
        data, "Install Python dependencies (validators + tests + import-linter)"
    )
    collectors_run = _validate_step_run(
        data, "Install coupling collectors (ungate coupling lens real-seam tests)"
    )
    assert f"dependency-cruiser@{adapters.DEPCRUISE_PIN}" in collectors_run
    assert f"typescript@{adapters.TYPESCRIPT_PIN}" in collectors_run
    assert f"import-linter>={adapters.IMPORT_LINTER_PIN}," in python_deps_run


def test_release_please_still_runs_check_release_bump():
    # Axis: post-merge backstop was not removed.
    with open(_RELEASE_WF) as fh:
        text = fh.read()
    assert "check_release_bump.py" in text
