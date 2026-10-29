"""A break-it test of a JavaScript project reaches the reviewed checkout's installed node_modules (#2034).

The fixture project is a scratch npm project whose only dependency is a fake ``vitest`` package, written
by the fixture, so no test installs anything or reaches the network."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from unittest import mock

import pytest

_LIB = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import break_it  # noqa: E402
import sanitized_view  # noqa: E402

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None or shutil.which("npm") is None,
    reason="node and npm are required to run a JavaScript break-it test")

# The fixture repo's commits pass an inline identity (a CI runner has no configured one).
_ID = ["-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]
PASSING = 'if (1 + 1 !== 2) throw new Error("bad");\n'
FAILING = 'throw new Error("bad");\n'
TEST_PATH = "src/x.test.mjs"
NPM_RUN = "npm test -- " + TEST_PATH
NPX_RUN = "npx vitest run " + TEST_PATH
PACKAGE = {"name": "p", "private": True, "type": "module", "scripts": {"test": "vitest run"},
           "devDependencies": {"vitest": "0.0.0-fake"}}
VITEST_BIN = """#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = fs.realpathSync(fileURLToPath(import.meta.url));
const modules = path.resolve(path.dirname(here), "..", "..");
fs.mkdirSync(path.join(modules, ".vite-temp"), { recursive: true });
fs.writeFileSync(path.join(modules, ".vite-temp", "config.txt"), "temp");
try {
  await import(pathToFileURL(path.join(process.cwd(), "vitest.config.mjs")).href);
  const files = process.argv.slice(2).filter((a) => a.endsWith(".test.mjs"));
  await import(pathToFileURL(path.resolve(process.cwd(), files[files.length - 1])).href);
  console.log("Test Files 1 passed (1)");
} catch (err) {
  console.log(String(err));
  process.exit(1);
}
"""


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("npm_config_cache", str(tmp_path / "npm-cache"))
    monkeypatch.setenv("npm_config_offline", "true")
    monkeypatch.setenv("npm_config_update_notifier", "false")
    monkeypatch.setenv("npm_config_fund", "false")
    monkeypatch.setenv("npm_config_audit", "false")


def _git(repo, *args):
    done = subprocess.run(["git", "-C", str(repo)] + list(args), capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return done.stdout


def _write(base, rel, text):
    target = base / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    return target


def _install_fake(base):
    """The fake vitest package under ``base`` (a node_modules directory), with its .bin link."""
    _write(base, "vitest/package.json", json.dumps({
        "name": "vitest", "version": "0.0.0-fake", "type": "module",
        "bin": {"vitest": "bin/vitest.mjs"}, "exports": {"./config": "./config.mjs"}}))
    _write(base, "vitest/config.mjs", "export const defineConfig = (c) => c;\n")
    _write(base, "vitest/bin/vitest.mjs", VITEST_BIN).chmod(0o755)
    (base / ".bin").mkdir(parents=True, exist_ok=True)
    os.symlink("../vitest/bin/vitest.mjs", base / ".bin" / "vitest")


def _repo(tmp_path, name="repo", *, install=True, track_modules=False, package=PACKAGE, tracked_local=False):
    """A committed scratch npm project; ``install`` writes the (untracked, ignored) node_modules."""
    root = tmp_path / name
    root.mkdir()
    _git(root, "init", "-q")
    _write(root, "package.json", json.dumps(package))
    if not track_modules:
        _write(root, ".gitignore", "node_modules/\n")
    _write(root, "vitest.config.mjs",
           'import { defineConfig } from "vitest/config"; export default defineConfig({});\n')
    _write(root, "README.md", "fixture\n")
    if tracked_local:
        _write(root, "packages/localpkg/index.js", "module.exports = 1;\n")
    if install:
        _install_fake(root / "node_modules")
    _git(root, "add", "-A")
    _git(root, *_ID, "commit", "-q", "-m", "base")
    return root


def _head(repo):
    return _git(repo, "rev-parse", "HEAD").strip()


def _block(content, run=NPM_RUN, path=TEST_PATH):
    return {"path": path, "run": run, "content": content,
            "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest()}


def _run(repo, content, run=NPM_RUN, path=TEST_PATH):
    return break_it.run_one(str(repo), _head(repo), _block(content, run, path), timeout=120)


def _tracked_hashes(repo):
    names = _git(repo, "ls-files", "-z").split("\0")
    return {n: hashlib.sha256((repo / n).read_bytes()).hexdigest() for n in names if n}


# T1
@pytest.mark.parametrize("content,outcome,code", [(PASSING, "passed", 0), (FAILING, "failed", 1)])
def test_t1_npm_script_resolves_the_installed_dependencies(tmp_path, content, outcome, code):
    got = _run(_repo(tmp_path), content, NPM_RUN)
    assert (got["outcome"], got["exitCode"]) == (outcome, code), got


# T2
@pytest.mark.parametrize("content,outcome", [(PASSING, "passed"), (FAILING, "failed")])
def test_t2_npx_shape_resolves_the_installed_dependencies(tmp_path, content, outcome):
    got = _run(_repo(tmp_path), content, NPX_RUN)
    assert got["outcome"] == outcome, got


# T3
def test_t3_no_install_is_not_run_module_not_found_and_launches_nothing(tmp_path):
    got = _run(_repo(tmp_path, install=False), PASSING, NPM_RUN)
    assert (got["outcome"], got["reason"]) == ("not-run", "module-not-found"), got
    assert got["exitCode"] is None
    assert "no installed node_modules" in got["output"]


def test_t3_without_the_gate_precondition_the_run_time_signature_still_fails_closed(tmp_path):
    bare = dict(PACKAGE)
    del bare["devDependencies"]
    got = _run(_repo(tmp_path, install=False, package=bare), PASSING, NPM_RUN)
    assert (got["outcome"], got["reason"], got["exitCode"]) == ("not-run", "command-not-found", 127), got


def test_t3_an_unparseable_package_json_fires_no_gate(tmp_path):
    repo = _repo(tmp_path, install=False)
    (repo / "package.json").write_text("not json {")
    _git(repo, "add", "-A")
    _git(repo, *_ID, "commit", "-q", "-m", "unparseable")
    got = _run(repo, PASSING, NPM_RUN)
    # the run launched (an exit code, not the gate's launch-nothing record) and reads as it does without the gate
    assert got["exitCode"] is not None, got
    assert "no installed node_modules" not in (got["output"] or ""), got
    assert got["outcome"] != "passed", got


# T4
def test_t4_npx_with_an_empty_offline_cache_is_not_run(tmp_path):
    got = _run(_repo(tmp_path, install=False), PASSING, NPX_RUN)
    assert (got["outcome"], got["reason"]) == ("not-run", "module-not-found"), got


def test_t4_npx_with_a_global_install_holding_the_fake_is_not_run(tmp_path, monkeypatch):
    prefix = tmp_path / "global"
    _install_fake(prefix / "lib" / "node_modules")
    (prefix / "bin").mkdir(parents=True)
    os.symlink("../lib/node_modules/vitest/bin/vitest.mjs", prefix / "bin" / "vitest")
    monkeypatch.setenv("npm_config_prefix", str(prefix))
    launched = mock.Mock(wraps=break_it._run_contained)
    monkeypatch.setattr(break_it, "_run_contained", launched)
    got = _run(_repo(tmp_path, install=False), PASSING, NPX_RUN)
    assert (got["outcome"], got["reason"], got["exitCode"]) == ("not-run", "module-not-found", None), got
    launched.assert_not_called()


# T5
def test_t5_a_tracked_file_the_run_writes_is_restored(tmp_path):
    repo = _repo(tmp_path)
    before = _tracked_hashes(repo)
    content = 'import fs from "node:fs"; fs.writeFileSync("README.md", "changed");\n' + PASSING
    got = _run(repo, content, NPM_RUN)
    assert got["outcome"] == "passed", got
    assert got["restored"] == ["test-file", "tracked"], got
    assert _tracked_hashes(repo) == before
    assert _git(repo, "status", "--porcelain") == ""
    # the installed (ignored) node_modules is the checkout's own, so the run's cache file stays in it
    assert (repo / "node_modules" / ".vite-temp" / "config.txt").is_file()


# T6
_THROUGH_THE_LINK = 'import fs from "node:fs"; fs.writeFileSync(%r, "changed");\n'


@pytest.mark.parametrize("link,target,written", [
    ("node_modules/localpkg", "../packages/localpkg", "node_modules/localpkg/index.js"),
    ("node_modules/@s/localpkg", "../../packages/localpkg", "node_modules/@s/localpkg/index.js"),
])
def test_t6_a_write_through_a_dependency_link_into_a_tracked_file_is_restored(tmp_path, link, target, written):
    repo = _repo(tmp_path, install=False, tracked_local=True)
    _install_fake(repo / "node_modules")
    (repo / link).parent.mkdir(parents=True, exist_ok=True)
    os.symlink(target, repo / link)
    before = _tracked_hashes(repo)
    got = _run(repo, _THROUGH_THE_LINK % written, "node " + TEST_PATH)
    assert got["outcome"] == "passed", got
    assert got["restored"] == ["test-file", "tracked"], got
    assert _tracked_hashes(repo) == before
    assert _git(repo, "status", "--porcelain") == ""


def test_t6_a_write_through_a_dependency_folder_that_links_into_the_checkout_is_restored(tmp_path):
    repo = _repo(tmp_path, install=False)
    _write(repo, "vendor/pkg/index.js", "module.exports = 1;\n")
    _git(repo, "add", "-A")
    _git(repo, *_ID, "commit", "-q", "-m", "vendor")
    os.symlink("vendor", repo / "node_modules")
    before = _tracked_hashes(repo)
    got = _run(repo, _THROUGH_THE_LINK % "node_modules/pkg/index.js", "node " + TEST_PATH)
    assert got["outcome"] == "passed", got
    assert got["restored"] == ["test-file", "tracked"], got
    assert _tracked_hashes(repo) == before
    # the link itself is an untracked file the .gitignore directory pattern does not match, and it stays
    assert _git(repo, "status", "--porcelain") == "?? node_modules\n"


def test_t6_a_write_through_a_bin_entry_linking_into_tracked_files_is_restored(tmp_path):
    repo = _repo(tmp_path, install=False)
    _write(repo, "scripts/tool.js", "console.log(1);\n")
    _git(repo, "add", "-A")
    _git(repo, *_ID, "commit", "-q", "-m", "scripts")
    _install_fake(repo / "node_modules")
    os.symlink("../../scripts/tool.js", repo / "node_modules" / ".bin" / "tool")
    before = _tracked_hashes(repo)
    got = _run(repo, _THROUGH_THE_LINK % "node_modules/.bin/tool", "node " + TEST_PATH)
    assert got["outcome"] == "passed", got
    assert got["restored"] == ["test-file", "tracked"], got
    assert _tracked_hashes(repo) == before
    assert _git(repo, "status", "--porcelain") == ""


# T8
def test_t8_a_block_path_under_node_modules_is_removed_after_the_run(tmp_path):
    path = "node_modules/x.test.mjs"
    repo = _repo(tmp_path)
    got = _run(repo, PASSING, "npm test -- " + path, path)
    assert got["outcome"] == "passed", got
    assert got["restored"] == ["test-file"], got
    assert not (repo / path).exists()
    assert (repo / "node_modules" / "vitest").is_dir()


# T9
def test_t9_a_head_that_tracks_node_modules_runs_in_its_own(tmp_path):
    repo = _repo(tmp_path, track_modules=True)
    got = _run(repo, PASSING, NPM_RUN)
    assert got["outcome"] == "passed", got
    # the run wrote its cache file into the tracked directory; the restore removed it again
    assert "untracked" in got["restored"], got
    assert not (repo / "node_modules" / ".vite-temp").exists()
    assert _git(repo, "status", "--porcelain", "--untracked-files=all") == ""


# T10
def test_t10_the_run_rules_and_the_sanitized_view_notice_name_the_working_copy_and_the_dependencies():
    assert "root of the session's own working copy, at the reviewed head" in break_it.RUN_RULES
    notice = sanitized_view.sanitized_view_notice({"headSha": "abc"})
    assert "no installed dependencies" in notice and "node_modules" in notice
