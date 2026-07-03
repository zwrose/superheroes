"""#170 portability: the spine lib must run from a COPY, against a repo that does NOT contain the
plugin source — the case the dogfood setup (running the plugin on its own repo) has hidden.

preflight.py resolves every sibling module + lib->lib subprocess call SCRIPT-DIR-relative
(`here = os.path.dirname(os.path.abspath(__file__))`), so a copy is self-sufficient. Running it
from a tmp copy against a scratch git repo therefore exercises exactly the off-source-repo path:
if any lib dependency resolved against the (absent) plugin source in the target repo, the verdict
would carry a ModuleNotFoundError / file-not-found instead of a clean fail-closed gate result.
"""
import json
import os
import shutil
import subprocess

LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _git(repo, *args):
    subprocess.run(["git", "-C", repo, *args], check=True, capture_output=True, text=True)


def test_preflight_runs_from_a_copy_against_a_foreign_repo(tmp_path):
    # 1. Copy the lib dir to a tmp path whose own path does NOT contain `plugins/superheroes/lib`
    #    (so a stray repo-relative resolution could not accidentally succeed).
    lib_copy = tmp_path / "spine_lib_copy"
    shutil.copytree(
        LIB, lib_copy,
        ignore=shutil.ignore_patterns("tests", "__pycache__", "fixtures", "parity", "*.pyc"),
    )
    assert "plugins/superheroes/lib" not in str(lib_copy)
    assert (lib_copy / "preflight.py").exists()

    # 2. A scratch git repo that does NOT contain the plugin source.
    repo = tmp_path / "foreign_repo"
    repo.mkdir()
    _git(str(repo), "init", "-q")
    _git(str(repo), "config", "user.email", "t@example.com")
    _git(str(repo), "config", "user.name", "t")
    (repo / "README.md").write_text("scratch\n")
    _git(str(repo), "add", "-A")
    _git(str(repo), "commit", "-q", "-m", "init")
    assert not (repo / "plugins" / "superheroes" / "lib").exists(), "the scratch repo must not contain the plugin source"

    # 3. Run preflight FROM THE COPY against the foreign repo. main() always emits a JSON verdict
    #    and exits 0/1; only a failure to resolve the lib from the copy would surface as an error.
    out = subprocess.run(
        ["python3", str(lib_copy / "preflight.py"), "--work-item", "wi-x", "--root", str(repo)],
        capture_output=True, text=True, timeout=90, cwd=str(tmp_path),
    )

    assert out.returncode in (0, 1), (
        "preflight crashed instead of emitting a verdict (portability regression):\n"
        + out.stdout + out.stderr
    )
    verdict = json.loads(out.stdout or "{}")
    # The gate ran end-to-end: every blocking check is present (decide() ran over a real probes dict).
    checks = {b["check"] for b in verdict.get("blocking", [])}
    assert {"spec-approved", "github-access", "no-active-run", "repo-ready",
            "verify-resolves", "config-resolves"} <= checks, verdict

    # The portability signal: NO import / file-not-found error — the lib resolved from the copy, not
    # from the (absent) plugin source in the target repo.
    err = (verdict.get("error") or "") + out.stderr
    for needle in ("ModuleNotFoundError", "ImportError", "No such file", "cannot import",
                   "No module named"):
        assert needle not in err, "lib failed to resolve from the copy (%r):\n%s" % (needle, err)
